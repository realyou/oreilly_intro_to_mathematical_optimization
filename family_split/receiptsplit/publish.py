"""Turn an allocation result into publish requests: one per target, with the
owed shares, the notes and a fingerprint for duplicate protection.

There is no Splitwise API access (it needs Splitwise Pro), so "publishing"
means rendering a paste-ready sheet and recording the entry in the local
ledger. The ledger (ledger.py) refuses a fingerprint it has already seen.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

from .engine import distribute
from .models import UNASSIGNED, Policy
from .notes import fmt_date, fmt_money, render_notes


def fingerprint(target: str, currency: str, cost_cents: int, lines: List[dict]) -> str:
    key = {"target": target, "currency": currency, "cost": cost_cents,
           "lines": sorted((l["receipt_id"], l["id"], l["card_cents"]) for l in lines)}
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16]


def build_publish_requests(result: dict, policy: Policy, batch_date: str, paid_by: Optional[str] = None) -> List[dict]:
    """One request per target that has a share rule. `unassigned` lines are
    returned as a request with status 'blocked' so they stay visible."""
    if not result.get("ok"):
        raise ValueError("allocation has errors; fix them before publishing")
    payers = {r["paid_by"] for r in result["receipts"]}
    if paid_by is None:
        if len(payers) != 1:
            raise ValueError(f"receipts have different payers {sorted(payers)}: pass paid_by explicitly or split the batch")
        paid_by = payers.pop()
    cur = result["card_currency"]
    reqs = []
    for target, block in result["targets"].items():
        cost = block["card_cents"]
        req = {
            "target": target, "label": policy.label(target),
            "description": f"{policy.label(target)} {fmt_date(batch_date, policy.date_format)}",
            "currency": cur, "cost_cents": cost, "cost": fmt_money(cost, cur, {}),
            "paid_by": paid_by, "notes": render_notes(block, cur, policy),
            "fingerprint": fingerprint(target, cur, cost, block["lines"]),
            "line_count": len(block["lines"]),
        }
        if target == UNASSIGNED:
            req.update({"status": "blocked", "owed_cents": {}, "reason": "assign these lines first"})
        else:
            shares = policy.shares(target)
            req["owed_cents"] = distribute(cost, shares, list(shares.keys())) if cost else {p: 0 for p in shares}
            req["status"] = "draft"
        reqs.append(req)
    return reqs


def render_sheet(requests: List[dict], policy: Policy) -> str:
    """Everything the user needs to type into Splitwise, in reading order."""
    parts = []
    for r in requests:
        head = [f"=== {r['label']} · {r['cost']} · {r['status'].upper()} ===",
                f"Description: {r['description']}",
                f"Paid by: {policy.people.get(r['paid_by'], r['paid_by'])}"]
        if r["owed_cents"]:
            head.append("Split: " + ", ".join(f"{policy.people.get(p, p)} {fmt_money(c, r['currency'], {})}" for p, c in r["owed_cents"].items()))
        else:
            head.append(f"Blocked: {r.get('reason', '')}")
        head.append(f"Fingerprint: {r['fingerprint']}")
        parts.append("\n".join(head) + "\n--- notes ---\n" + r["notes"])
    return "\n\n".join(parts) + "\n"
