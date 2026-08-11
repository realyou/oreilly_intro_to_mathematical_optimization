#!/usr/bin/env python3
"""lexical search over the knowledge base.

    python3 kb_search.py "b12 levels" [--root DIR] [--limit 10] [--all]

ranks by where the match landed — id and title beat aliases and tags, which beat body text —
then prints the path, the id, and the matching lines. that ordering is the whole trick: at
personal-knowledge scale, exact ids, aliases, tags and dates find the right note faster than
any embedding, and the result is explainable.

by default superseded records are ranked last and historical ones are marked, so a search
does not quietly hand back something the user already corrected. `--all` keeps everything
at full weight.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kbio  # noqa: E402

WEIGHTS = {"id": 12, "title": 8, "alias": 7, "tag": 5, "heading": 3, "body": 1, "path": 2}


def score_file(path: Path, root: Path, terms: list[str], include_all: bool):
    fm, body, _ok, text = kbio.read(path)
    low = text.lower()
    if not all(t in low for t in terms):
        # every term must appear somewhere; ranking then decides where it counts most.
        return None

    ident = str(fm.get("id") or "")
    title = ""
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    aliases = fm.get("aliases") or []
    tags = fm.get("tags") or []
    if isinstance(aliases, str):
        aliases = [aliases]
    if isinstance(tags, str):
        tags = [tags]

    headings = " ".join(l for l in body.splitlines() if l.startswith("#"))
    rel = str(path.relative_to(root))

    score = 0
    for t in terms:
        if t in ident.lower():
            score += WEIGHTS["id"]
        if t in title.lower():
            score += WEIGHTS["title"]
        if any(t in str(a).lower() for a in aliases):
            score += WEIGHTS["alias"]
        if any(t in str(g).lower() for g in tags):
            score += WEIGHTS["tag"]
        if t in headings.lower():
            score += WEIGHTS["heading"]
        if t in rel.lower():
            score += WEIGHTS["path"]
        score += min(low.count(t), 5) * WEIGHTS["body"]

    status = str(fm.get("record_status") or "")
    if not include_all:
        if status == "superseded":
            score = score * 0.2
        elif status in ("historical", "resolved"):
            score = score * 0.7

    hits = []
    for i, line in enumerate(text.splitlines(), start=1):
        ll = line.lower()
        if any(t in ll for t in terms):
            hits.append((i, line.strip()[:160]))
        if len(hits) >= 3:
            break

    return {"path": rel, "id": ident, "title": title, "status": status,
            "score": score, "hits": hits}


def main():
    ap = argparse.ArgumentParser(description="lexical search over a life knowledge base")
    ap.add_argument("query", nargs="+")
    ap.add_argument("--root", default="life-os/life-knowledge-base")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--all", action="store_true",
                    help="do not down-rank superseded and historical records")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    terms = [t.lower() for t in re.split(r"\s+", " ".join(args.query)) if t]
    results = [r for r in (score_file(p, root, terms, args.all)
                           for p in kbio.iter_markdown(root)) if r]
    results.sort(key=lambda r: (-r["score"], r["path"]))

    if not results:
        print(f"no matches for {' '.join(terms)!r} in {root}")
        print("nothing found is a real answer — do not fill the gap from memory.")
        return 0

    for r in results[:args.limit]:
        flag = f"  [{r['status']}]" if r["status"] and r["status"] != "current" else ""
        print(f"\n{r['path']}{flag}")
        if r["id"] or r["title"]:
            print(f"  {r['id']}  {r['title']}".rstrip())
        for line_no, snippet in r["hits"]:
            print(f"  {line_no}: {snippet}")

    extra = len(results) - args.limit
    if extra > 0:
        print(f"\n… and {extra} more matches (--limit to see them)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
