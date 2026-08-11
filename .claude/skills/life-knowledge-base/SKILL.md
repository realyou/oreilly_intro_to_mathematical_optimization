---
name: life-knowledge-base
description: >
  read, search, capture, and correct the user's personal knowledge base. use when the user
  shares durable personal context (health, projects, goals, people, decisions, documents,
  preferences), asks a question about their own life or history, saves a document or url,
  corrects something previously recorded, or asks what is known about a topic. also use
  before answering any personal question, to avoid answering from stale memory.
version: 1.0.0
tags: [knowledge-base, memory, capture, retrieval, provenance, privacy]
kb_path: life-os/life-knowledge-base
---

# life-knowledge-base

the knowledge base is the detailed source of truth about the user. this skill is how you read
and write it without corrupting it.

**always read `life-os/life-knowledge-base/agent_rules.md` first.** it outranks this file, and
it holds the user's own rules: what to call them, their timezone, and what must never be
stored.

## the one-paragraph version

files are the truth. memory is a pointer. every consequential claim is either sourced or
labelled as a report, an observation, a preference, or a hypothesis. corrections never delete.
a routine update costs one targeted write and one short acknowledgement — not a project.

## when to use this skill

| situation | what to do |
| --- | --- |
| user shares durable context | capture workflow, below |
| user asks about their own life | retrieval workflow, below |
| user saves a url | hand off to `resource-library` |
| user corrects something | correction workflow, below |
| user shares a document | intake: preserve original, source record, one summary |
| user mentions a goal or ambition | hand off to `goal-planning`, then link back here |
| user asks for a review | hand off to `life-review` |

## capture workflow

1. **is it durable and useful?** transient chatter is not captured. cheap and unsure →
   `01-inbox/inbox.md`.
2. **search before writing.**
   ```bash
   python3 .claude/skills/life-knowledge-base/scripts/kb_search.py "<terms>"
   ```
   never create a second note for something that already has one.
3. **append to today's existing event note** rather than creating fragments.
4. **preserve the user's wording** where nuance matters. quote it.
5. **write the smallest authoritative set of files.**
6. **update a canonical summary only if current understanding changed.** a data point that
   confirms the summary does not edit the summary.
7. **preserve corrections and superseded history.**
8. **verify with one search** — read back what you wrote.
9. **acknowledge in one line**: what was written, where, and any estimate you made.

## retrieval workflow

1. read `agent_rules.md`.
2. search the files — not your memory of them.
3. read the canonical summary for the domain.
4. read newer events and entity notes; a summary can be stale by design.
5. follow `source_ids` for anything consequential.
6. separate current / historical / resolved / uncertain / superseded.
7. state uncertainty and conflicts explicitly.
8. cite note paths, ids, and dates when accuracy matters.
9. obey the user's stated scope and exclusions literally.

## correction workflow

the user says something you recorded is wrong.

1. find the existing record. do not guess which one it is — search.
2. write the new record with `supersedes: [old-id]`.
3. set the old record's `record_status: superseded`. **do not delete its text.**
4. update the canonical summary to reflect the corrected understanding.
5. if the correction conflicts with a source document, record the conflict in
   `00-index/open_questions.md` rather than deciding who is right.
6. say what changed and what is now superseded.

## document intake

1. copy the original, unmodified, into `90-sources/files/`.
2. create `90-sources/records/src-YYYYMMDD-NNN.md` from the source template.
3. add a row to `00-index/sources_index.md`.
4. write **one** source-grounded summary; every claim cites the source id.
5. deep normalization only when the user asks. an unextracted original is honest.

## privacy floor

never write: credentials, passwords, cookies, recovery codes, api keys, seed phrases, payment
authentication, portal logins, 2fa codes. if the user pastes one, say you did not store it.

never send knowledge-base content to a third party — web search, api, email, paste service,
issue tracker — without explicit approval for that specific destination.

## scripts

```bash
# validate: ids, dates, frontmatter, links, csv headers, secret-shaped strings
python3 .claude/skills/life-knowledge-base/scripts/kb_validate.py life-os/life-knowledge-base

# lexical search over the knowledge base (ids, aliases, tags, titles, body)
python3 .claude/skills/life-knowledge-base/scripts/kb_search.py "b12 levels" --limit 10

# rebuild the derivative search manifest + index counts
python3 .claude/skills/life-knowledge-base/scripts/kb_index.py life-os/life-knowledge-base
```

scripts print findings only. they never print the contents of anything secret-shaped, and they
never write outside the knowledge base.

search order: **lexical search, ids, aliases, tags, dates, one-hop links.** embeddings are not
needed at personal-knowledge scale and are not part of this system.

## pitfalls

- **answering from memory.** you remember a summary, not the file. read the file.
- **editing an event to reflect new understanding.** events are what happened. supersede
  instead.
- **fanning one remark into six files.** one targeted write.
- **filling an empty field with something plausible.** empty stays empty.
- **upgrading a user report into a fact** because it was repeated. only a source does that.
- **inventing a day** when the user said "a couple of years ago". use `date_precision`.
- **resolving a conflict silently** because one side seems more likely. record both.
- **duplicating a fact** into a summary and an event. one writable copy; the rest link.
- **normalizing a large import** nobody asked you to normalize.
- **treating chat history as proof.** it is context, not state.

## verification checklist

before saying you captured something:

- [ ] i searched for an existing authoritative note first
- [ ] every consequential claim has a source id or an epistemic label
- [ ] dates are ISO, in the user's timezone, with precision recorded when not exact
- [ ] corrections carry `supersedes` and the old record still exists
- [ ] no secret was written to disk
- [ ] i read back what i wrote with one search
- [ ] the acknowledgement says where it landed, in one line

before answering a personal question:

- [ ] i read `agent_rules.md` this turn
- [ ] i read the canonical summary and any newer records
- [ ] i separated current from historical, resolved, uncertain, and superseded
- [ ] i stated conflicts and uncertainty instead of smoothing them
- [ ] every claim traces to a file i read in this turn
