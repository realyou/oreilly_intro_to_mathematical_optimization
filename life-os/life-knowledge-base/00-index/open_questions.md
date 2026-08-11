---
id: idx-open-questions
type: index
record_status: current
updated: 2026-08-11
---

# open questions and recorded conflicts

when two records disagree, both stay on disk and the disagreement is recorded here. this
file is the reason the system never has to silently pick a winner.

## how to use this file

| column | meaning |
| --- | --- |
| id | `q-YYYYMMDD-NNN` |
| question | what is not known, in one sentence |
| why it matters | what decision or answer it blocks |
| records involved | ids and paths of the conflicting or incomplete records |
| what would resolve it | the specific document, measurement, or user answer needed |
| status | `open` / `resolved` / `parked` |

resolving a question means: adding the resolving record, setting the superseded record's
`record_status`, and marking the row `resolved` with the date — not deleting the row.

## open

| id | question | why it matters | records involved | what would resolve it | status |
| --- | --- | --- | --- | --- | --- |
| q-20260811-001 | the four onboarding questions in `10-profile/profile.md` are unanswered | no personal capture can be dated, addressed, or privacy-filtered correctly | [profile](../10-profile/profile.md) | the user answering them | open |

## resolved

_none._
