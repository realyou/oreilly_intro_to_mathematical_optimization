---
id: projects-summary
type: index
subtype: project
record_status: current
updated: 2026-08-11
---

# projects summary

one line per project. the detail lives in [projects/](projects/), one note per durable
project. task state lives in the tracker.

| id | project | status | phase | next action | note |
| --- | --- | --- | --- | --- | --- |
| _none recorded_ | | | | | |

## what every active project note captures

- **purpose and desired outcome** — what is true when this is done
- **status and current phase**
- **owner and collaborators** — and who decides
- **target users** — who it is for, when that applies
- **scope and non-goals** — non-goals are load-bearing; write them down
- **architecture or operating model** — how the thing works
- **current priorities**
- **decisions and rationale** — `dec-` records; the rationale is what you will need later
- **constraints, risks, metrics, deadlines, review triggers**
- **links, repositories, documents, source records**
- **next actions** — pointing at the tracker, not duplicating facts from this note

## separation that matters

facts, assumptions, forecasts, decisions, and experiments are five different things and live
in five labelled sections. an assumption promoted to a fact needs a source and a date; it
does not get promoted by being repeated.

any time-sensitive metric carries an `as_of` date and a source. a metric without one is
treated as unknown, not as still-true.

## project health

health comes from explicit rules: are the milestones moving, is there an unblocked next
action, is the deadline still reachable given what is done. never a percentage derived from
elapsed time, and never a number invented to look like progress.

## archiving

completed and abandoned projects keep their notes and their decisions. the reason for
abandoning is recorded — that reason is often the most valuable line in the file.
