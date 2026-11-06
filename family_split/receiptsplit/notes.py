"""Render the itemized notes block for one target, in the agreed format:

    Apotekku — 06 Nov 2026
    $4.77 Youvit Multivitamin for Kids (30 days)

    Pepito Market — 06 Nov 2026
    $3.04 Merries diapers L
    ----
    Total: $8.55
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List

from .models import Policy

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt_date(iso: str, fmt: str = "%d %b %Y") -> str:
    """English month names regardless of the process locale."""
    d = date.fromisoformat(iso)
    return fmt.replace("%d", f"{d.day:02d}").replace("%b", _MONTHS[d.month - 1]).replace("%Y", str(d.year))


def fmt_money(cents: int, currency: str, symbols: Dict[str, str]) -> str:
    sign = "-" if cents < 0 else ""
    body = f"{abs(cents) // 100:,}.{abs(cents) % 100:02d}"
    sym = symbols.get(currency.upper())
    return f"{sign}{sym}{body}" if sym else f"{sign}{currency.upper()} {body}"


def render_notes(target_block: dict, currency: str, policy: Policy) -> str:
    """`target_block` is one entry of allocate()['targets']. Lines are grouped
    by receipt in first-seen order; a blank line separates receipts."""
    sections: List[List[str]] = []
    seen: Dict[str, int] = {}
    for row in target_block["lines"]:
        key = row["receipt_id"]
        if key not in seen:
            seen[key] = len(sections)
            sections.append([f"{row['merchant']} — {fmt_date(row['date'], policy.date_format)}"])
        sections[seen[key]].append(f"{fmt_money(row['card_cents'], currency, policy.currency_symbols)} {row['name']}")
    out = "\n\n".join("\n".join(s) for s in sections)
    out += "\n----\nTotal: " + fmt_money(target_block["card_cents"], currency, policy.currency_symbols)
    return out
