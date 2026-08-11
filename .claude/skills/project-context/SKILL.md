---
name: project-context
description: >
  create and maintain project notes and project state — purpose, scope, non-goals, decisions,
  constraints, risks, metrics, blockers, milestones, tasks, and the next executable action.
  use when the user starts or discusses a project, asks where a project stands, records a
  decision, hits a blocker, or asks what to do next on it. also use before planning or
  executing project work, to load current state instead of working from a stale summary.
version: 1.0.0
tags: [projects, decisions, milestones, blockers, state]
---

# project-context

a project note exists so that six weeks from now, you or the user can rebuild the whole
context in two minutes — including why the obvious-looking alternative was rejected.

## before planning or executing anything

1. read the project note (`50-projects/projects/prj-slug.md`).
2. read newer dated records that mention the project — a summary is stale by design.
3. read the tracker row for current tasks, blockers, and next action.
4. only then plan.

skipping step 2 is how you confidently propose something the user abandoned last month.

## what a project note captures

- **purpose and desired outcome** — what is true when this is done
- **status and current phase**
- **owner and collaborators** — and who decides
- **target users** — who it is for, when that applies
- **scope** and **non-goals** — non-goals prevent more rework than anything else here
- **architecture or operating model** — how the thing actually works
- **current priorities**
- **decisions and rationale** — `dec-` records
- **constraints, risks, metrics, deadlines, review triggers**
- **links** — repositories, documents, source records
- **next actions** — a pointer to the tracker, not a second copy of the facts

## five things that must stay separate

| kind | label | test |
| --- | --- | --- |
| fact | verified, sourced | could you show someone the evidence? |
| assumption | believed, unverified | what would confirm it? |
| forecast | `epistemic: hypothesis` | it is about the future; it is not knowledge |
| decision | `dec-` record | it foreclosed an alternative |
| experiment | tried, with a result | what changed because of it? |

an assumption becomes a fact when a source says so — never by being repeated in three
meetings. every time-sensitive metric carries an `as_of` date and a source; without one, treat
it as unknown rather than still-true.

## decisions

record a decision when it forecloses an alternative. capture what was decided, the context
that forced it, **the alternatives considered and why each lost**, the rationale, the cost
accepted, and the revisit trigger.

the alternatives section is the part you will actually want later. a decision with no recorded
cost was probably not a decision.

## tracker side

```bash
T=".claude/skills/life-tracker/scripts/tracker.py"
python3 $T project-add --title "build the site" --goal 2 --phase build \
  --deadline 2026-09-01 --kb-path life-os/life-knowledge-base/50-projects/projects/prj-site.md \
  --tasks "pick a generator" "write first page"
python3 $T task-add --title "photograph the bench" --project 1
python3 $T project-set 1 --set blocker="electrician has not confirmed a date"
python3 $T projects            # status, health, next action
```

## health and progress

**health** comes from explicit rules and always shows its reasons: is there a blocker, is
there an open next action, are milestones moving against the deadline. it is a label with an
explanation, never a mood and never a number.

**progress** comes from explicit milestones or task scope. never from elapsed time. a project
three weeks into a four-week plan is not 75% done; that is a calendar, not a status.

if scope is not defined, report "scope not defined" — do not manufacture a denominator.

## archiving

completed and abandoned projects keep their notes, their decisions, and their reasons. archive
finished tasks; never delete the decisions that produced them. pausing or abandoning requires
a reason, enforced by the api.

## pitfalls

- planning from the note alone when newer records exist.
- a project note with scope but no non-goals.
- decisions recorded as outcomes, with the alternatives lost.
- a metric with no `as_of` date, quietly treated as current.
- inventing a completion percentage.
- health as a vibe instead of a rule with reasons.
- duplicating task state into the note, so the note and the tracker disagree within a week.
- letting "next action" become a wish rather than something executable.

## verification checklist

- [ ] i read the note **and** newer dated records **and** the tracker row
- [ ] scope and non-goals are both written down
- [ ] facts, assumptions, forecasts, decisions and experiments are separated and labelled
- [ ] every consequential metric has an `as_of` date and a source
- [ ] there is one executable next action, or a stated reason there cannot be
- [ ] blockers name what is blocked and what would unblock it
- [ ] progress has a stated basis; health has its reasons attached
- [ ] the note holds prose, the tracker holds state, and neither duplicates the other
