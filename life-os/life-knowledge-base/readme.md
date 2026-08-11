# life knowledge base

portable, private, file-based. plain markdown, no proprietary format, no lock-in. copy the
directory and it still works.

**if you are an agent: read `agent_rules.md` before doing anything else.**

## what is where

| path | holds |
| --- | --- |
| `agent_rules.md` | the rules every agent follows. authoritative. |
| `00-index/` | entry points: master index, people, projects, sources, open questions |
| `01-inbox/inbox.md` | unprocessed capture, cleared or linked once normalized |
| `10-profile/profile.md` | who the user is, stable facts, foundation answers |
| `20-timeline/` | `timeline.md` summary + dated event notes under `events/YYYY/` |
| `30-health/` | summary + conditions, medications, procedures, tests, logs |
| `40-nutrition/` | summary + logs |
| `50-projects/` | summary + one note per durable project |
| `60-finance/` | summary (balances and account numbers are **not** stored here) |
| `70-goals/` | summary + one note per goal |
| `75-ideas/` | index + one note per idea |
| `80-interests/` | interests summary |
| `85-resources/resources.md` | curated external resources, categorized |
| `90-sources/` | `files/` original documents, `records/` one source record each |
| `95-system/` | schema, changelog, intake, backups, templates |

## the two questions this structure answers

- **"what is true now?"** → the canonical summary for the domain.
- **"what happened, and when?"** → the dated event and entity notes.

a summary that grows a history section is a bug. an event note that gets edited to reflect
new understanding is also a bug — write a new record and mark the old one superseded.

## conventions

- dates are `YYYY-MM-DD`, in the user's timezone (see `agent_rules.md` §2).
- every consequential claim carries a source id or an epistemic label.
- one writable copy of any fact; everything else links.
- corrections never delete. superseded records stay readable and traceable.
- derivatives (indexes, csv, charts, sqlite, search manifest) are rebuildable, never the truth.

## related pieces of the system

- **tracker** — `../tracker/`, the private life operating system (today / goals / projects /
  data). authoritative for dated completions and observations; linked to these notes by id.
- **skills** — `../../.claude/skills/`, the reusable agent skills that read and write both.
- **memory pointer** — `../../CLAUDE.md`, which tells future sessions this directory exists.
