"""Allocation engine: receipt lines -> targets -> card currency, exact to the cent.

Two rounding levels, both largest remainder, both deterministic:
1. Receipt level: the receipt's extras (total minus the sum of its lines: tax,
   service, rounding, receipt-wide discount) are spread over the positive
   lines in proportion to their printed price. Result: a gross amount per
   line in receipt cents that sums exactly to the receipt total.
2. Card level: the amount actually charged to the card is spread over the
   lines in proportion to their gross receipt cents. Result: a card amount
   per line that sums exactly to the card charge.
Targets are then simple sums of line card cents, so every invariant in
CONTRACTS.md holds by construction.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence

from .models import REVIEW_THRESHOLD, UNASSIGNED, Allocation, Issue, Policy, Receipt


def distribute(total: int, weights: Dict[str, float], order: Optional[Sequence[str]] = None) -> Dict[str, int]:
    """Split integer `total` by `weights` (may be negative) so the parts sum
    exactly to `total`. Largest-remainder rounding; ties go to the earlier
    key in `order` (default: insertion order). Weights that are all zero
    raise ValueError: the caller must decide what "nothing to weigh" means."""
    keys = list(order) if order is not None else list(weights.keys())
    wsum = sum(weights.get(k, 0) for k in keys)
    if not keys or wsum == 0:
        raise ValueError("cannot distribute over zero total weight")
    raw = {k: total * weights.get(k, 0) / wsum for k in keys}
    base = {k: math.floor(raw[k]) for k in keys}
    leftover = total - sum(base.values())
    # leftover is in [0, len(keys)) because each floor drops less than 1
    by_remainder = sorted(keys, key=lambda k: (-(raw[k] - base[k]), keys.index(k)))
    for k in by_remainder[:leftover]:
        base[k] += 1
    assert sum(base.values()) == total
    return base


def _validate_receipt(r: Receipt, issues: List[Issue]) -> None:
    if r.total_cents <= 0:
        issues.append(Issue("error", "receipt total must be positive", r.id))
    if not r.lines:
        issues.append(Issue("error", "receipt has no lines", r.id))
    if r.subtotal_cents is not None and r.subtotal_cents != r.lines_sum:
        issues.append(Issue("warning", f"printed subtotal {r.subtotal_cents} differs from line sum {r.lines_sum}", r.id))
    parts = [r.subtotal_cents, r.tax_cents, r.service_cents, r.discount_cents]
    if all(p is not None for p in parts):
        expected = r.subtotal_cents + r.tax_cents + r.service_cents - r.discount_cents
        if expected != r.total_cents:
            issues.append(Issue("warning", f"subtotal + tax + service - discount = {expected}, total printed {r.total_cents}", r.id))
    if all(l.price_cents <= 0 for l in r.lines):
        issues.append(Issue("error", "no positive line to carry the extras", r.id))
    seen = set()
    for l in r.lines:
        if l.id in seen:
            issues.append(Issue("error", "duplicate line id", r.id, l.id))
        seen.add(l.id)
        if l.confidence is not None and l.confidence < REVIEW_THRESHOLD:
            issues.append(Issue("warning", f"low extraction confidence {l.confidence:.2f}, check against the photo", r.id, l.id))


def _validate_allocation(r: Receipt, a: Allocation, policy: Policy, issues: List[Issue]) -> None:
    if a.receipt_id != r.id:
        issues.append(Issue("error", f"allocation is for receipt {a.receipt_id}", r.id))
    if a.paid_by not in policy.people:
        issues.append(Issue("error", f"unknown payer '{a.paid_by}'", r.id))
    line_ids = {l.id for l in r.lines}
    for lid, target in a.targets.items():
        if lid not in line_ids:
            issues.append(Issue("error", f"allocation names unknown line '{lid}'", r.id, lid))
        if target != UNASSIGNED and not policy.shares(target):
            issues.append(Issue("error", f"target '{target}' has no share rule in the policy", r.id, lid))
        if target.startswith("personal:") and target.split(":", 1)[1] not in policy.people:
            issues.append(Issue("error", f"target '{target}' names an unknown person", r.id, lid))
    for l in r.lines:
        if a.target_of(l.id) == UNASSIGNED:
            issues.append(Issue("warning", "line is unassigned", r.id, l.id))
    if a.card_amount_cents is not None and a.card_amount_cents <= 0:
        issues.append(Issue("error", "card amount must be positive", r.id))
    if a.card_amount_cents is not None and not a.card_currency:
        issues.append(Issue("error", "card amount given without a currency", r.id))


def gross_lines(r: Receipt) -> Dict[str, int]:
    """Receipt cents per line including its proportional share of the extras."""
    order = [l.id for l in r.lines]
    gross = {l.id: l.price_cents for l in r.lines}
    extras = r.extras_cents
    if extras:
        weights = {l.id: l.price_cents for l in r.lines if l.price_cents > 0}
        for lid, c in distribute(extras, weights, [k for k in order if k in weights]).items():
            gross[lid] += c
    assert sum(gross.values()) == r.total_cents
    return gross


def allocate(receipts: Iterable[Receipt], allocations: Iterable[Allocation], policy: Policy) -> dict:
    """Run the two-level allocation for a batch. Never raises on bad data: the
    result's `issues` list carries errors, and `ok` is False when any error
    exists. Returns a JSON-serializable dict (see CONTRACTS.md)."""
    receipts = list(receipts)
    alloc_by_id = {a.receipt_id: a for a in allocations}
    issues: List[Issue] = []
    out_receipts = []
    targets: Dict[str, dict] = {}
    card_currency: Optional[str] = None

    for r in receipts:
        _validate_receipt(r, issues)
        a = alloc_by_id.get(r.id)
        if a is None:
            issues.append(Issue("error", "no allocation for this receipt", r.id))
            continue
        _validate_allocation(r, a, policy, issues)
        if any(i.level == "error" and i.receipt_id == r.id for i in issues):
            continue

        # level 1: receipt cents
        gross = gross_lines(r)
        # level 2: card cents
        if a.card_amount_cents is not None:
            cur, card_total = a.card_currency.upper(), a.card_amount_cents
        elif a.rate:
            cur, card_total = (a.card_currency or r.currency).upper(), round(r.total_cents * a.rate)
        else:
            cur, card_total = r.currency, r.total_cents
        if card_currency is None:
            card_currency = cur
        elif cur != card_currency:
            issues.append(Issue("error", f"card currency {cur} differs from the batch's {card_currency}", r.id))
            continue
        card = distribute(card_total, {lid: g for lid, g in gross.items()}, [l.id for l in r.lines])

        lines_out = []
        for l in r.lines:
            t = a.target_of(l.id)
            row = {"id": l.id, "name": l.name, "qty": l.qty, "target": t, "receipt_cents": l.price_cents,
                   "receipt_gross_cents": gross[l.id], "card_cents": card[l.id]}
            lines_out.append(row)
            tb = targets.setdefault(t, {"card_cents": 0, "lines": []})
            tb["card_cents"] += card[l.id]
            tb["lines"].append({**row, "receipt_id": r.id, "merchant": r.merchant, "date": r.date})
        out_receipts.append({
            "id": r.id, "merchant": r.merchant, "date": r.date, "paid_by": a.paid_by,
            "receipt_currency": r.currency, "receipt_total_cents": r.total_cents, "extras_cents": r.extras_cents,
            "card_currency": cur, "card_total_cents": card_total,
            "implied_rate": card_total / r.total_cents, "lines": lines_out,
        })

    errors = [i for i in issues if i.level == "error"]
    return {
        "ok": not errors,
        "card_currency": card_currency,
        "card_total_cents": sum(x["card_total_cents"] for x in out_receipts),
        "receipts": out_receipts,
        "targets": targets,
        "issues": [i.to_dict() for i in issues],
    }
