#!/usr/bin/env python3
"""validate the knowledge base: ids, dates, frontmatter, links, csv headers, secrets.

    python3 kb_validate.py life-os/life-knowledge-base [--quiet]

exit 0 clean, 1 errors found, 2 could not run. warnings alone do not fail the run.

this script reads. it never writes, never edits, and never prints the contents of anything
that matched a secret pattern — only the file and line, so the finding is actionable without
copying the secret into a terminal, a log, or a transcript.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kbio  # noqa: E402

# patterns for things that must never be committed. matching is deliberately loose: a false
# positive costs one look, a false negative costs a leaked credential.
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
    (re.compile(r"\b(sk|pk)-[A-Za-z0-9]{16,}\b"), "api key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "github token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws access key id"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "slack token"),
    (re.compile(r"(?i)\b(password|passwd|passphrase|secret|api[_ -]?key|token|"
                r"seed phrase|recovery code|cvv|pin)\b\s*[:=]\s*\S+"), "credential assignment"),
    (re.compile(r"(?i)\b(?:\w+\s+){11,23}\w+\b(?=.*\bseed\b)"), "possible seed phrase"),
]
# lines that talk *about* secrets rather than containing one.
SAFE_CONTEXT = re.compile(
    r"(?i)(never|not|do not|don't|no)\s+(store|write|record|save|commit|keep|put)"
    r"|must never|never store|_unanswered_|<[^>]+>|TBD|`[^`]*`")


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, path, msg, line=None):
        self.errors.append((path, line, msg))

    def warn(self, path, msg, line=None):
        self.warnings.append((path, line, msg))


def validate(root: Path, rep: Report):
    ids: dict[str, Path] = {}
    referenced: list[tuple[Path, str, str]] = []
    files = list(kbio.iter_markdown(root))
    if not files:
        rep.error(root, "no markdown files found — is this a knowledge base?")
        return ids

    for path in files:
        rel = path.relative_to(root)
        fm, body, ok, text = kbio.read(path)
        if not ok:
            rep.error(rel, "frontmatter block opened with '---' but never closed")
            continue

        scan_secrets(rel, text, rep)
        check_links(root, path, rel, body, rep)

        if not fm:
            continue
        if kbio.is_template(path, fm):
            continue

        ident = fm.get("id")
        if ident:
            ident = str(ident)
            if ident in ids:
                rep.error(rel, f"duplicate id '{ident}', also in {ids[ident]}")
            else:
                ids[ident] = rel
            known = ("index", "person", "profile", "changelog", "intake", "backups",
                     "inbox", "timeline", "resources")
            if not ident.startswith(kbio.ID_PREFIXES) and \
                    not any(k in ident for k in known) and \
                    fm.get("type") not in ("index",):
                rep.warn(rel, f"id '{ident}' uses no known prefix "
                              f"({', '.join(kbio.ID_PREFIXES)})")

        for field in kbio.DATE_FIELDS:
            v = fm.get(field)
            if v in (None, "", []):
                continue
            if not kbio.ISO_RE.match(str(v)):
                rep.error(rel, f"{field}='{v}' is not an ISO date (YYYY-MM-DD, YYYY-MM, YYYY)")
            elif len(str(v)) < 10 and not fm.get("date_precision"):
                rep.warn(rel, f"{field}='{v}' is less precise than a day but "
                              "date_precision is not set")

        occurred, recorded = fm.get("occurred_at"), fm.get("recorded_at")
        if occurred and recorded and len(str(occurred)) == 10 == len(str(recorded)):
            if str(occurred) > str(recorded):
                rep.error(rel, f"occurred_at {occurred} is after recorded_at {recorded}")

        vf, vt = fm.get("valid_from"), fm.get("valid_to")
        if vf and vt and str(vf) > str(vt):
            rep.error(rel, f"valid_from {vf} is after valid_to {vt}")

        enum_check(rel, fm, "record_status", kbio.RECORD_STATUS, rep)
        enum_check(rel, fm, "epistemic", kbio.EPISTEMIC, rep)
        enum_check(rel, fm, "confidence", kbio.CONFIDENCE, rep)
        enum_check(rel, fm, "verification", kbio.VERIFICATION, rep)

        for field in ("supersedes", "source_ids"):
            vals = fm.get(field) or []
            if isinstance(vals, str):
                vals = [vals]
            for v in vals:
                referenced.append((rel, field, str(v)))

        if str(fm.get("record_status")) == "superseded" and not fm.get("superseded_by"):
            rep.warn(rel, "record_status is 'superseded' but superseded_by is not set — "
                          "the replacement should be findable from here")

    for rel, field, ref in referenced:
        if ref not in ids:
            rep.error(rel, f"{field} points at '{ref}', which no record defines")

    check_csv(root, rep)
    return ids


def enum_check(rel, fm, field, allowed, rep):
    v = fm.get(field)
    if v in (None, "", []):
        return
    # templates aside, a pipe means the author left the choices in place
    if "|" in str(v):
        rep.warn(rel, f"{field}='{v}' still lists the options instead of choosing one")
        return
    if str(v) not in allowed:
        rep.error(rel, f"{field}='{v}' is not one of {sorted(allowed)}")


def check_links(root: Path, path: Path, rel: Path, body: str, rep: Report):
    for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", body):
        target = m.group(1).split("#")[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "<")):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            line = body[:m.start()].count("\n") + 1
            rep.error(rel, f"link target does not exist: {target}", line)


def check_csv(root: Path, rep: Report):
    """csv exports are derivatives; a ragged one means the generator is broken."""
    for p in sorted(root.rglob("*.csv")):
        rel = p.relative_to(root)
        try:
            with p.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.reader(fh))
        except Exception as e:
            rep.error(rel, f"unreadable csv: {type(e).__name__}")
            continue
        if not rows:
            rep.warn(rel, "empty csv")
            continue
        width = len(rows[0])
        for i, row in enumerate(rows[1:], start=2):
            if row and len(row) != width:
                rep.error(rel, f"row {i} has {len(row)} fields, header has {width}")
                break


def scan_secrets(rel: Path, text: str, rep: Report):
    for i, line in enumerate(text.splitlines(), start=1):
        if SAFE_CONTEXT.search(line):
            continue
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(line):
                # the location, never the value.
                rep.error(rel, f"possible {label} on this line — secrets must never be "
                               "stored in the knowledge base", i)
                break


def main():
    ap = argparse.ArgumentParser(description="validate a life knowledge base")
    ap.add_argument("root", nargs="?", default="life-os/life-knowledge-base")
    ap.add_argument("--quiet", action="store_true", help="errors only")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    rep = Report()
    ids = validate(root, rep)

    if rep.errors:
        print(f"errors ({len(rep.errors)})")
        for path, line, msg in rep.errors:
            print(f"  {path}{':' + str(line) if line else ''}: {msg}")
    if rep.warnings and not args.quiet:
        print(f"warnings ({len(rep.warnings)})")
        for path, line, msg in rep.warnings:
            print(f"  {path}{':' + str(line) if line else ''}: {msg}")

    n_files = len(list(kbio.iter_markdown(root)))
    print(f"\nchecked {n_files} markdown files, {len(ids)} identified records — "
          f"{len(rep.errors)} errors, {len(rep.warnings)} warnings")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
