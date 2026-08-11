---
name: life-review
description: >
  run a daily, weekly, monthly, or quarterly review across goals, projects, habits, and
  metrics. use when the user asks how their week or month went, asks for a review or a
  check-in, wants to know what is stalled or blocked, or when a scheduled goal review date has
  arrived. produces observations, a small number of decisions, and next actions — not a
  scoreboard and not a lecture.
version: 1.0.0
tags: [review, reflection, weekly, monthly, trends]
---

# life-review

a review reads state and reports it. it is **not** a cron job that rewrites the record: it
does not duplicate canonical records, it does not silently change statuses, and it does not
create a new document every week that nobody reads.

## what a review reads

```bash
T=".claude/skills/life-tracker/scripts/tracker.py"
python3 $T data --days 7            # or 30 / 90
python3 $T goals
python3 $T projects
python3 $T trend --habit <id> --days 30
python3 .claude/skills/life-knowledge-base/scripts/kb_search.py "<domain>" --limit 5
```

plus, for anything consequential, the knowledge-base notes behind it.

## the four cadences

| cadence | horizon | asks |
| --- | --- | --- |
| **daily** | today | what got done, what is left, what is blocked right now |
| **weekly** | 7 days | habit consistency, project movement, goals with no next action |
| **monthly** | 30 days | milestone progress, metric trends with coverage, what stalled |
| **quarterly** | 90 days | are these still the right goals? what should be dropped? |

each is short. a weekly review that takes twenty minutes to read will not happen twice.

## the shape of a review

1. **what happened** — completed actions, milestones met, metrics with enough coverage to say
   anything. facts only.
2. **what did not move** — stalled goals, projects with no open next action, blockers still
   blocking, habits below their usual consistency.
3. **observations** — patterns visible in the data, labelled as observations.
4. **explanations** — kept separate from observations, and labelled as hypotheses. "sleep was
   lower this week" is an observation; "because of the deadline" is a hypothesis, even when it
   is obvious.
5. **a small number of decisions** — two or three, not a list of twelve.
6. **next actions** — concrete, and attached to something.

## rules

- **distinguish observation from explanation**, always. the data shows what happened; it does
  not explain why, and you were not there.
- **never imply causation** among habits, metrics, goals, health, or projects. co-movement is
  not cause, and a personal dataset of thirty days can support almost nothing.
- **coverage with every number.** "7.1 h mean across 9 logged days of 30" — not "7.1 h".
  if coverage is thin, say the data cannot support a conclusion.
- **update a status only with evidence or user confirmation.** a goal that looks stalled is a
  question for the user, not a status change you make on their behalf.
- **no guilt language.** no "you failed to", "only", "just", "should have". a missed week is
  information, not a verdict.
- **do not turn every metric into a target.** something can be tracked because it is
  interesting. a metric with no target is not a metric that is failing.
- **missed days are not the story.** recovery is. report consistency and how quickly things
  resumed, never streaks.
- **an empty week is a valid result.** say "nothing was logged this week, so there is nothing
  to report" rather than assembling something from thin evidence.

## what a review may write

- a dated review note in `20-timeline/events/YYYY/` when the user wants it kept.
- an entry in `00-index/open_questions.md` for a question the review surfaced.
- status changes **only** when the user confirms them in the conversation.

it does not rewrite summaries, restructure goals, or create projects. those belong to
`goal-planning` and `project-context`, with the user in the loop.

## pitfalls

- reporting an average with no coverage.
- explaining a trend you cannot support, in confident language.
- silently marking a goal `blocked` because it looked quiet.
- a review that is really a performance evaluation.
- weekly review notes that duplicate the tracker, so the truth now lives in two places.
- optimizing the metric that is easiest to move rather than the one that matters.
- listing twelve next actions, which is the same as listing none.

## verification checklist

- [ ] every number carries its coverage
- [ ] observations and explanations are separately labelled
- [ ] no causal claim is made from co-movement
- [ ] no status was changed without evidence or explicit confirmation
- [ ] the language is neutral — no guilt, no praise inflation
- [ ] the review names at most three decisions and concrete next actions
- [ ] thin data was reported as thin, not padded out
