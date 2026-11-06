"""Data shapes for receiptsplit. Plain dataclasses that mirror CONTRACTS.md."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

UNASSIGNED = "unassigned"
REVIEW_THRESHOLD = 0.6


@dataclass
class Line:
    id: str
    name: str
    price_cents: int
    qty: float = 1
    raw: str = ""
    confidence: Optional[float] = None


@dataclass
class Receipt:
    id: str
    merchant: str
    date: str  # ISO yyyy-mm-dd
    currency: str
    lines: List[Line]
    total_cents: int
    subtotal_cents: Optional[int] = None
    tax_cents: Optional[int] = None
    service_cents: Optional[int] = None
    discount_cents: Optional[int] = None
    source: dict = field(default_factory=dict)

    @property
    def lines_sum(self) -> int:
        return sum(l.price_cents for l in self.lines)

    @property
    def extras_cents(self) -> int:
        """Tax, service, rounding, receipt-level discount: whatever sits between the lines and the total."""
        return self.total_cents - self.lines_sum

    @staticmethod
    def from_dict(d: dict) -> "Receipt":
        lines = [Line(id=str(l["id"]), name=str(l["name"]), price_cents=int(l["price_cents"]), qty=l.get("qty", 1),
                      raw=l.get("raw", ""), confidence=l.get("confidence")) for l in d["lines"]]
        return Receipt(id=str(d["id"]), merchant=str(d["merchant"]), date=str(d["date"]), currency=str(d["currency"]).upper(),
                       lines=lines, total_cents=int(d["total_cents"]), subtotal_cents=d.get("subtotal_cents"),
                       tax_cents=d.get("tax_cents"), service_cents=d.get("service_cents"),
                       discount_cents=d.get("discount_cents"), source=d.get("source", {}))

    @staticmethod
    def load(path: Path | str) -> "Receipt":
        return Receipt.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class Allocation:
    receipt_id: str
    paid_by: str
    targets: Dict[str, str]  # line id -> target
    card_currency: Optional[str] = None
    card_amount_cents: Optional[int] = None
    rate: Optional[float] = None  # used only when card_amount_cents is absent

    def target_of(self, line_id: str) -> str:
        return self.targets.get(line_id, UNASSIGNED)

    @staticmethod
    def from_dict(d: dict) -> "Allocation":
        card = d.get("card") or {}
        return Allocation(receipt_id=str(d["receipt_id"]), paid_by=str(d["paid_by"]),
                          targets={str(k): str(v["target"] if isinstance(v, dict) else v) for k, v in (d.get("lines") or {}).items()},
                          card_currency=(card.get("currency") or None), card_amount_cents=card.get("amount_cents"),
                          rate=d.get("rate"))

    @staticmethod
    def load(path: Path | str) -> "Allocation":
        return Allocation.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class Policy:
    people: Dict[str, str]
    targets: Dict[str, dict]  # target -> {"label": str, "shares": {person: weight}}
    date_format: str = "%d %b %Y"
    currency_symbols: Dict[str, str] = field(default_factory=lambda: {"USD": "$", "EUR": "€", "GBP": "£"})

    def label(self, target: str) -> str:
        t = self.targets.get(target)
        if t and t.get("label"):
            return t["label"]
        if target.startswith("personal:"):
            return self.people.get(target.split(":", 1)[1], target) + " only"
        return target.capitalize()

    def shares(self, target: str) -> Dict[str, float]:
        t = self.targets.get(target)
        if t and t.get("shares"):
            return dict(t["shares"])
        if target.startswith("personal:"):
            return {target.split(":", 1)[1]: 1}
        return {}

    @staticmethod
    def from_dict(d: dict) -> "Policy":
        notes = d.get("notes") or {}
        return Policy(people=dict(d["people"]), targets=dict(d.get("targets") or {}),
                      date_format=notes.get("date_format", "%d %b %Y"),
                      currency_symbols=dict(notes.get("currency_symbols") or {"USD": "$", "EUR": "€", "GBP": "£"}))

    @staticmethod
    def load(path: Path | str) -> "Policy":
        return Policy.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class Issue:
    level: str  # "error" | "warning"
    message: str
    receipt_id: Optional[str] = None
    line_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}
