"""Command line: run a batch of receipts through the engine.

    python -m receiptsplit preview  --policy fixtures/policy.json --date 2026-11-06 \
        fixtures/receipts/apotekku.json:fixtures/allocations/apotekku.json \
        fixtures/receipts/pepito.json:fixtures/allocations/pepito.json

    python -m receiptsplit publish --ledger data/ledger.json ...same arguments...
    python -m receiptsplit done --ledger data/ledger.json <fingerprint> [reference]

`preview` prints issues and the paste-ready sheet. `publish` additionally
records every request as a draft in the ledger and refuses fingerprints it
has seen. `done` marks a draft as entered in Splitwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import allocate
from .ledger import Ledger
from .models import Allocation, Policy, Receipt
from .publish import build_publish_requests, render_sheet


def _load_pairs(pairs):
    receipts, allocations = [], []
    for p in pairs:
        rp, ap = p.split(":", 1)
        receipts.append(Receipt.load(rp))
        allocations.append(Allocation.load(ap))
    return receipts, allocations


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="receiptsplit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("preview", "publish"):
        s = sub.add_parser(name)
        s.add_argument("--policy", required=True)
        s.add_argument("--date", required=True, help="batch date, yyyy-mm-dd, used in descriptions")
        s.add_argument("--paid-by", default=None)
        s.add_argument("--json", action="store_true", help="print the allocation result as JSON instead of the sheet")
        if name == "publish":
            s.add_argument("--ledger", required=True)
        s.add_argument("pairs", nargs="+", help="receipt.json:allocation.json")
    d = sub.add_parser("done")
    d.add_argument("--ledger", required=True)
    d.add_argument("fingerprint")
    d.add_argument("reference", nargs="?", default="")
    args = ap.parse_args(argv)

    if args.cmd == "done":
        led = Ledger(args.ledger)
        e = led.mark_published(args.fingerprint, args.reference)
        print(f"published: {e['label']} {e['cost']} {e['currency']}")
        return 0

    policy = Policy.load(args.policy)
    receipts, allocations = _load_pairs(args.pairs)
    result = allocate(receipts, allocations, policy)
    for i in result["issues"]:
        where = ":".join(x for x in (i.get("receipt_id"), i.get("line_id")) if x)
        print(f"[{i['level']}] {where}: {i['message']}", file=sys.stderr)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1
    if not result["ok"]:
        print("errors above: nothing to publish", file=sys.stderr)
        return 1
    reqs = build_publish_requests(result, policy, args.date, args.paid_by)
    if args.cmd == "publish":
        led = Ledger(args.ledger)
        for r in reqs:
            if r["status"] != "draft":
                continue
            prior = led.seen(r["fingerprint"])
            if prior:
                r["status"] = f"duplicate of {prior['status']} entry from {prior['recorded_at']}"
            else:
                led.record_draft(r)
    print(render_sheet(reqs, policy))
    return 0


if __name__ == "__main__":
    sys.exit(main())
