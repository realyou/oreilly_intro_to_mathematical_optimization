---
id: intake
type: index
record_status: current
updated: 2026-08-11
---

# intake

how new material enters the knowledge base.

## 1. conversational capture

the common case. the user says something durable in passing.

1. decide it is durable and useful. if unsure and cheap → `01-inbox/inbox.md`.
2. search for the authoritative note.
3. append to today's existing event note if there is one; otherwise create one.
4. update the canonical summary **only if current understanding changed**.
5. read back what you wrote.
6. acknowledge in one line.

target cost: one write, one line back. do not escalate a passing remark into a project.

## 2. documents

pdfs, exports, photos of paperwork, statements, lab reports.

1. copy the original into `90-sources/files/` — unmodified, original filename preserved
   where possible.
2. create a source record in `90-sources/records/src-YYYYMMDD-NNN.md` with origin, provider,
   document date, received date, path, extraction status, reliability.
3. add a row to `00-index/sources_index.md`.
4. write **one** source-grounded summary. every claim cites the source id.
5. deep normalization (splitting into entity notes, extracting every value) happens only when
   the user asks. an unextracted original is honest; a half-invented extraction is not.

## 3. urls

follow `85-resources/resources.md` rules. read the source first, or store no summary.

## 4. bulk imports and exports

preserve the original, create one source record, summarize once. do not fan a 400-row export
into 400 notes. if the data is genuinely tabular and dated, it usually belongs in the tracker
as observations, with the export preserved as its source.

## 5. what to refuse

- credentials and secrets of any kind — not stored, and say so.
- third-party personal data beyond what retrieval requires.
- anything the user's privacy exclusions cover.

## verification

after any intake, run:

```bash
python3 ../../../.claude/skills/life-knowledge-base/scripts/kb_validate.py .
```

it checks ids, dates, links, frontmatter, and secret-shaped strings. it prints findings only,
never the contents of anything that looks like a secret.
