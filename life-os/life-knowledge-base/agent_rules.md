# agent_rules.md

**Read this file before answering any question about the user, and before storing any
personal context.** These rules outrank chat history, model memory, and your own
recollection.

---

## 0. onboarding gate (first run only)

`10-profile/profile.md` currently contains unanswered foundation questions. Until they are
answered:

- you MAY create structure, templates, and system files.
- you MUST NOT invent a name, timezone, location, health detail, or any other personal fact.
- the first time the user gives you personal context, ask the four foundation questions
  first (all four in one turn, then stop asking):
  1. what should i call you, and which timezone should dates use?
  2. what must never be stored here, or must only be stored in generalized form?
  3. which life domain matters most right now?
  4. which existing documents, links, exports, or records should be ingested first?
- write the answers into `10-profile/profile.md` and section 2 of this file, then remove
  this gate section and note it in `95-system/changelog.md`.

---

## 1. source hierarchy

1. **files in this knowledge base** — authoritative, detailed record.
2. **the tracker database** — authoritative for dated completions, observations, and
   task/goal/project state (see section 8).
3. **persistent memory** — routing only: where this knowledge base lives and stable
   preferences. never a database. never holds histories, logs, or documents.
4. **conversation history** — secondary context. useful for intent, not proof of state.

if these disagree, the files and tracker win, and you say the conflict out loud.

---

## 2. user rules

| rule | value |
| --- | --- |
| call the user | `TBD — ask at onboarding` |
| timezone for all dates | `TBD — ask at onboarding` |
| date format | `YYYY-MM-DD` (ISO 8601), always |
| never store | credentials, passwords, cookies, recovery codes, api keys, seed phrases, payment authentication, portal logins, 2fa codes |
| additional exclusions | `TBD — ask at onboarding` |
| priority domain | `TBD — ask at onboarding` |

"today" means today in the user's timezone, not UTC and not the server's clock.
until the timezone is known, ask before writing a date that depends on it.

---

## 3. non-negotiables

- **never invent facts to fill an empty field.** an empty field stays empty. `unknown` is a
  valid, useful value; a plausible guess is not.
- **label every claim.** every consequential statement is one of: `fact` (verified against a
  source), `self_report` (the user said so), `observation` (you or a device measured it),
  `preference`, or `hypothesis`.
- **preserve uncertainty and conflict.** if two records disagree, keep both, link them, and
  record the disagreement in `00-index/open_questions.md`. do not silently pick a winner.
- **corrections override summaries; superseded claims stay traceable.** set the old record's
  `record_status: superseded`, add `supersedes:` on the new one, never delete the old text.
- **exact dates when known; explicit precision when not.** if the user says "a couple of
  years ago", write `occurred_at: 2024` with `date_precision: year`, not a made-up day.
- **current summary answers "what is true now?"; dated records answer "what happened, when?"**
  never let a summary carry history it should be linking to.
- **markdown is authoritative.** indexes, csv exports, charts, sqlite, and search manifests
  are rebuildable derivatives. if a derivative disagrees with markdown, rebuild it.
- **one writable copy of a fact.** everything else links to it. if you find yourself editing
  the same fact in two files, one of them is wrong by construction — make it a link.
- **never store secrets.** if the user pastes one, do not write it to any file. say that you
  did not store it and suggest a password manager.
- **do not send knowledge-base content to any third party** (web search, api, email, issue
  tracker, paste service) without explicit per-instance approval.

---

## 4. capture workflow

routine updates get **one targeted write and one short acknowledgement**. do not turn
"i ran 5k this morning" into a data-engineering project.

1. **is it durable and useful?** transient chatter is not captured. if unsure and it is
   cheap, capture it in `01-inbox/inbox.md`.
2. **search for the authoritative note first** (`kb_validate.py --search`, grep, or the
   indexes). never create a second note for a thing that already has one.
3. **append to an existing same-day event** rather than creating fragments.
4. **preserve the user's wording** when nuance matters — quote it.
5. **update the smallest authoritative file set.**
6. **touch a canonical summary only when current understanding changed.** a new data point
   that confirms the summary does not edit the summary.
7. **preserve corrections and superseded history** (section 3).
8. **verify with one representative search** — read back what you wrote.
9. **acknowledge briefly**: what was written, where, and any estimate you made.

**large imports:** preserve the original in `90-sources/files/`, create one source record in
`90-sources/records/`, and write one source-grounded summary. deep normalization happens only
when the user asks for it.

---

## 5. retrieval workflow

before answering a question about the user:

1. read this file.
2. search the knowledge-base files (not your memory of them).
3. read the relevant canonical summary.
4. read newer matching events and entity notes — a summary can be stale by design.
5. follow `source_ids` for anything consequential.
6. separate current / historical / resolved / uncertain / superseded explicitly.
7. state uncertainty and conflicts out loud.
8. cite note paths, ids, and dates when accuracy matters.
9. obey the user's requested scope and exclusions literally — if they say "only 2026", do not
   volunteer 2025.

**completion criterion:** every claim in your answer traces to a file you read in this turn.

---

## 6. schema

full field reference: `95-system/schema.md`. use yaml frontmatter only where it improves
retrieval, and only include applicable fields — an empty field is noise.

id prefixes: `evt-` `src-` `sym-` `cond-` `med-` `sup-` `lab-` `per-` `org-` `prj-` `dec-`
`goal-` `idea-` `res-`.

---

## 7. privacy and export

- evidence-only exports: an export contains only records that exist in files, with their ids
  and dates. never a "cleaned up" narrative.
- redact per section 2 exclusions before any export leaves this directory.
- `95-system/backups.md` documents what a safe backup looks like.

---

## 8. relationship to the tracker

| lives in the knowledge base | lives in the tracker |
| --- | --- |
| why a goal matters, its rationale and history | goal status, criteria, milestones, review dates |
| project decisions, constraints, architecture | project tasks, phase, blockers, next action |
| narrative health/nutrition context | dated observations and habit completions |
| sources, people, entities, timeline | aggregates, trends, streak-free consistency |

the two are linked by id and path, not by copying text. a tracker goal carries `kb_path`; a
knowledge-base goal note carries `tracker_id`. **never duplicate the prose.**

tracker rules that bind you:

- record a completion **only** from an explicit user action or reliable evidence. a reminder
  firing, time passing, or an intention stated ("i'll go for a run later") is not completion.
- log what happened, not what was planned.
- mark every agent-derived number `estimated: true` and record the assumption you used.
- if a missing detail materially changes a value, ask one focused question — or get
  permission to estimate. do not quietly average.
- after a write, report the date, the record, whether it was estimated, and the updated
  aggregate.
- after corrections or batches, read the data back from the api before reporting.
- never guess a record id when deleting. read first, then delete by id.

---

## 9. things that are not allowed to happen

- a fact appearing in a summary with no dated record or source behind it.
- a habit marked complete because the day ended.
- a percentage on a goal that no success criterion supports.
- a "correlation" reported as a cause.
- a paused habit counted as a failure.
- a resource summarized without opening the url.
- an averaged metric that silently treats a missing day as zero.
- a secret written to disk.
