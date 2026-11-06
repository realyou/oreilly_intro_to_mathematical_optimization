"""Local ledger: the system of record for what has been entered in Splitwise.

A JSON file, one entry per publish request fingerprint. Refuses duplicates.
Keep the ledger file out of Git (see .gitignore): it is personal data.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class Ledger:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.entries: Dict[str, dict] = {}
        if self.path.exists():
            self.entries = json.loads(self.path.read_text(encoding="utf-8")).get("entries", {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"entries": self.entries}, indent=2, ensure_ascii=False), encoding="utf-8")

    def seen(self, fp: str) -> Optional[dict]:
        return self.entries.get(fp)

    def record_draft(self, req: dict) -> dict:
        """Store a request as 'draft'. A fingerprint already recorded is
        returned unchanged and never overwritten: that is the duplicate guard."""
        fp = req["fingerprint"]
        if fp in self.entries:
            return self.entries[fp]
        self.entries[fp] = {**{k: v for k, v in req.items() if k != "notes"}, "notes": req["notes"],
                            "status": req.get("status", "draft"),
                            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self.save()
        return self.entries[fp]

    def mark_published(self, fp: str, reference: str = "") -> dict:
        e = self.entries[fp]
        if e["status"] == "published":
            raise ValueError(f"{fp} is already published ({e.get('reference', '')})")
        e.update({"status": "published", "reference": reference,
                  "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        self.save()
        return e

    def drafts(self) -> List[dict]:
        return [e for e in self.entries.values() if e["status"] == "draft"]
