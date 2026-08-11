---
name: goal-planning
description: >
  turn a broad ambition into an outcome, a definition of done, success criteria, milestones,
  supporting projects and habits, and a next action. use when the user says they want to
  achieve, start, get better at, or finally do something; when a goal needs restructuring,
  pausing, or abandoning; when they ask what to work on next toward a goal; or when a goal
  review is due. do not use it to log completions — that is life-tracker.
version: 1.0.0
tags: [goals, planning, milestones, habits, review]
---

# goal-planning

converts ambitions into structures small enough to execute, and keeps the goal note and the
tracker in step without duplicating truth.

## the hierarchy

```text
life area
└── goal
    ├── success criteria      (how you will know)
    ├── milestones            (checkpoints)
    │   └── projects / workstreams
    │       └── next actions and checklists
    └── recurring habits      (the behavior that supports it)
```

build the **smallest** structure that makes the next step obvious. a goal may need only a
checklist. inventing three projects for a goal that needed one habit is how a plan dies.

## the conversation, in order

1. **outcome** — what is true when this is achieved? in the user's words.
2. **definition of done** — the unambiguous test. someone else could check it.
3. **baseline** — where things stand now, dated. without a baseline, progress is unmeasurable
   and every later claim about it is invented. if it is unknown, say so and make finding it
   the first action.
4. **constraints** — time, money, health, other commitments. real ones, not aspirational.
5. **success criteria** — a small number, each measurable. three good ones beat nine.
6. **milestones** — checkpoints, with the next one identified.
7. **projects or workstreams** — only where a milestone needs real work organized.
8. **habits** — the recurring behavior that supports it.
9. **next action** — one concrete thing that can be done now. if action is genuinely not
   possible yet, say that instead of manufacturing a task.
10. **review cadence and adjustment trigger** — when to look again, and the condition that
    means the plan should change rather than be pushed harder.

## keep the user's priorities

do not invent goals. do not quietly upgrade a passing "i should probably..." into a tracked
goal with milestones. ask whether they want it tracked.

if the user's ambition is vague, the job is to help them make it specific — not to substitute
a specific goal of your own and present it as theirs.

## writing it down — both places, once

| goes in the goal note (`70-goals/goals/goal-slug.md`) | goes in the tracker |
| --- | --- |
| rationale, baseline evidence, constraints, history | status, criteria, milestones, review date |
| why it matters, what was rejected | supporting projects, habits, next actions |
| status changes and their reasons | progress derived from criteria |

link them: the note carries `tracker_id`, the tracker row carries `kb_path`. the prose lives
in exactly one place.

```bash
T=".claude/skills/life-tracker/scripts/tracker.py"
python3 $T goal-add --title "run a 10k" --area health \
  --outcome "finish a 10k without walking" \
  --dod "crossed a measured 10k finish line" \
  --baseline "longest run 4 km as of 2026-07-01" \
  --criteria "run 10 km without stopping" "finish under 60 minutes" \
  --milestones "run 5 km" "run 8 km" --review 2026-09-01 \
  --kb-path life-os/life-knowledge-base/70-goals/goals/goal-run-10k.md
```

## progress, honestly

progress comes from **success criteria met**, else **milestones completed**, else it is
**qualitative** and gets no number. the tracker enforces this; do not work around it by
quoting a percentage in prose.

never derive progress from elapsed time, task count, or effort. "60% of the time has gone" is
not 60% done, and "12 sessions logged" is activity volume, not outcome progress.

some goals are binary. some are milestone-based. some carry a percentage. some can only be
reviewed qualitatively. use the one that fits and say which you used.

## status changes

`not_started` · `active` · `blocked` · `paused` · `completed` · `abandoned`

pausing, blocking, or abandoning **requires a reason** — the api rejects it otherwise. the
reason is the most valuable thing the record will ever hold: it is what stops the same goal
being re-litigated in six months, and what makes an abandonment a decision rather than a
failure.

```bash
python3 $T goal-set 4 --set status=paused status_reason="knee injury, revisit after 2026-10"
```

history is never deleted. a completed or abandoned goal keeps its note.

## pitfalls

- a goal with no definition of done — nobody can ever call it finished.
- criteria that cannot be checked ("get healthier", "be more consistent").
- nine criteria. it means the goal is really three goals.
- a milestone that is actually the goal restated.
- a next action that is a wish ("figure out nutrition") rather than an action.
- a percentage nobody's criteria support.
- confusing the habit with the goal: running three times a week is not "run a 10k".
- claiming a habit caused an outcome.
- restructuring a goal the user did not ask you to restructure.
- letting the note and the tracker drift into two versions of the same fact.

## verification checklist

- [ ] the outcome is in the user's words, and the definition of done is checkable
- [ ] there is a dated baseline, or an explicit "baseline unknown" with an action to find it
- [ ] criteria are few and measurable
- [ ] the next milestone and one concrete next action exist, or i said why they cannot
- [ ] a review date and an adjustment trigger are set
- [ ] the goal note and tracker row are linked, with no duplicated prose
- [ ] any status change carries its reason
- [ ] progress reported has a basis, and i named it
