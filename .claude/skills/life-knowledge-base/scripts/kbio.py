"""shared reading helpers for the knowledge-base scripts.

deliberately dependency-free: a knowledge base you can only read with a pip install is not
portable. this parses the small subset of yaml the schema actually uses — scalars, inline
lists, and `- item` blocks — and nothing more.
"""

from __future__ import annotations

import re
from pathlib import Path

ID_PREFIXES = ("evt-", "src-", "sym-", "cond-", "med-", "sup-", "lab-", "per-", "org-",
               "prj-", "dec-", "goal-", "idea-", "res-")

DATE_FIELDS = ("occurred_at", "valid_from", "valid_to", "recorded_at", "created", "updated",
               "diagnosed_at", "document_date", "received_at", "accessed_at", "started_at",
               "target_date", "next_review", "met_at")

RECORD_STATUS = {"current", "historical", "resolved", "uncertain", "superseded"}
EPISTEMIC = {"fact", "self_report", "observation", "hypothesis", "preference"}
CONFIDENCE = {"high", "medium", "low"}
VERIFICATION = {"verified", "user_reported", "unverified"}

ISO_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
TEMPLATE_TOKENS = ("YYYY-MM-DD", "YYYYMMDD", "yyyy-mm-dd", "nnn", "NNN", "-slug")


def split_frontmatter(text: str):
    """return (frontmatter_dict, body, ok). ok is False when a '---' block failed to close."""
    if not text.startswith("---"):
        return {}, text, True
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text, False
    raw = text[3:end].strip("\n")
    body = text[end + 4:]
    return parse_yaml_ish(raw), body, True


def parse_yaml_ish(raw: str) -> dict:
    out, key = {}, None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")) and line.lstrip().startswith("- ") and key:
            out.setdefault(key, [])
            if isinstance(out[key], list):
                out[key].append(_scalar(line.lstrip()[2:]))
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        key = k.strip()
        v = v.strip()
        if v == "":
            out[key] = []
        elif v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            out[key] = [_scalar(x) for x in inner.split(",") if x.strip()] if inner else []
        else:
            out[key] = _scalar(v)
    return out


def _scalar(v: str):
    v = v.strip().strip('"').strip("'")
    if v in ("null", "~", ""):
        return None
    if v == "true":
        return True
    if v == "false":
        return False
    return v


def is_template(path: Path, fm: dict) -> bool:
    """templates carry placeholder ids on purpose and must not be validated as records."""
    if "95-system/templates" in str(path).replace("\\", "/"):
        return True
    ident = str(fm.get("id") or "")
    return any(tok in ident for tok in TEMPLATE_TOKENS)


def iter_markdown(root: Path):
    for p in sorted(root.rglob("*.md")):
        yield p


def read(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body, ok = split_frontmatter(text)
    return fm, body, ok, text
