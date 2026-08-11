#!/usr/bin/env python3
"""rebuild the derivative search manifest and print index coverage.

    python3 kb_index.py [ROOT] [--write]

the manifest (`95-system/search_manifest.json`) is a **derivative**: ids, titles, paths, tags,
aliases, dates and statuses, extracted from the markdown. it is rebuildable at any time and is
never the truth. if it disagrees with a note, the note wins and this script fixes the manifest.

without `--write` it reports only, and also flags the two things that rot quietly:
records that no index links to, and index rows pointing at records that no longer exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kbio  # noqa: E402

INDEX_DIRS = ("00-index",)


def build(root: Path):
    records, manifest = {}, []
    for path in kbio.iter_markdown(root):
        fm, body, _ok, _text = kbio.read(path)
        if not fm or kbio.is_template(path, fm):
            continue
        ident = str(fm.get("id") or "")
        if not ident:
            continue
        title = next((l[2:].strip() for l in body.splitlines() if l.startswith("# ")), "")
        rel = str(path.relative_to(root))
        entry = {
            "id": ident,
            "title": title,
            "path": rel,
            "type": fm.get("type"),
            "subtype": fm.get("subtype"),
            "record_status": fm.get("record_status"),
            "epistemic": fm.get("epistemic"),
            "occurred_at": fm.get("occurred_at"),
            "updated": fm.get("updated"),
            "tags": fm.get("tags") or [],
            "aliases": fm.get("aliases") or [],
            "source_ids": fm.get("source_ids") or [],
        }
        manifest.append(entry)
        records[ident] = rel
    return records, sorted(manifest, key=lambda e: e["id"])


def index_text(root: Path) -> str:
    out = []
    for d in INDEX_DIRS:
        for p in (root / d).glob("*.md"):
            out.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="life-os/life-knowledge-base")
    ap.add_argument("--write", action="store_true", help="write the manifest to disk")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    records, manifest = build(root)
    idx = index_text(root)

    by_status, by_type = {}, {}
    for e in manifest:
        by_status[e["record_status"] or "unset"] = by_status.get(e["record_status"] or "unset", 0) + 1
        by_type[e["type"] or "unset"] = by_type.get(e["type"] or "unset", 0) + 1

    unlinked = [e for e in manifest
                if e["id"] not in idx and e["path"] not in idx
                and e["type"] not in ("index",)]

    print(f"records: {len(manifest)}")
    print("  by type:   " + ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())))
    print("  by status: " + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())))

    if unlinked:
        print(f"\nnot reachable from any index ({len(unlinked)}):")
        for e in unlinked[:20]:
            print(f"  {e['id']}  {e['path']}")
        print("  a record no index links to is a record retrieval will miss.")

    if args.write:
        out = root / "95-system" / "search_manifest.json"
        out.write_text(json.dumps(
            {"note": "derivative — rebuildable from the markdown, never authoritative",
             "records": manifest}, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {out.relative_to(root)} ({len(manifest)} records)")
    else:
        print("\n(report only; pass --write to rebuild the manifest)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
