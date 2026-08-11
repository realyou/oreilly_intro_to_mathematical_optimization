---
id: health-summary
type: index
subtype: health
record_status: current
updated: 2026-08-11
---

# health summary

what is true now. history lives in dated records and entity notes.

> this file is not medical advice and is not a clinical record. it is the user's own notes.
> for anything consequential, reopen the source document and involve a clinician.

## active conditions

_none recorded._ → [conditions/](conditions/)

## current medications and supplements

_none recorded._ → [medications/](medications/)

each medication note records: name, dose, schedule, prescriber, start date, reason, and
`valid_to` when stopped. a dose change creates a new record that supersedes the old one — the
old dose stays readable with its own validity window.

## recent tests and results

_none recorded._ → [tests/](tests/)

lab values are `epistemic: fact` **only** when a source document backs them. a value the user
recalls is `self_report` with `confidence: medium` at best, and stays that way until the
document arrives.

## procedures and events

_none recorded._ → [procedures/](procedures/)

## symptoms being tracked

_none recorded._ symptoms use `sym-` ids and link to the conditions they may relate to —
*may*. a symptom appearing alongside a condition is not evidence that one caused the other.

## logs

day-to-day measurements live in the tracker as dated observations, not here.
narrative context lives in [logs/](logs/).

## rules for this domain

- never infer a diagnosis, never suggest one, never upgrade a symptom into a condition.
- record what the user reported and what a document says, separately and labelled.
- a missing measurement is `unknown`, never zero.
- conflicts between a user report and a document stay as conflicts, recorded in
  [open_questions](../00-index/open_questions.md).
