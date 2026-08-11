---
name: life-tracker
description: >
  read and write the user's private life tracker — today's checklist, habits and routines,
  tasks, dated life metrics, and trends. use when the user reports that they did something
  ("ran 5k", "slept about seven hours", "took my meds", "finished that task"), asks what is on
  for today, wants a habit or metric created, corrected, paused or removed, or asks how a
  habit or metric has been going. do not use it to interpret meaning — that is life-review.
version: 1.0.0
tags: [tracker, habits, metrics, checklist, logging, timezone]
server: life-os/tracker/server.py
client: .claude/skills/life-tracker/scripts/tracker.py
---

# life-tracker

the tracker is authoritative for dated completions and observations. the knowledge base is
authoritative for meaning. keep prose in the knowledge base and numbers here, linked by id —
never copy one into the other.

## setup

```bash
python3 life-os/tracker/server.py          # http://127.0.0.1:8787
export LIFE_TRACKER_URL=http://127.0.0.1:8787
```

the client reads the token from `life-os/tracker/.token`. never print it, never paste it into
a message, never pass it as a command-line argument.

**the timezone must be set before anything dated is logged.** the api returns 409 rather than
guessing utc:

```bash
python3 .claude/skills/life-tracker/scripts/tracker.py settings-set --set timezone=Europe/Berlin
```

## the rule that matters most

**record a completion only from an explicit user action or reliable evidence.**

| the user said | do |
| --- | --- |
| "i ran this morning" | log it |
| "i'll go for a run later" | nothing. that is an intention |
| "remind me to run" | nothing. a reminder is not a completion |
| *the day ended* | nothing. time passing is not evidence |
| "i skipped the run today, rest day" | record state `skipped` — not a miss |

logging an intention as a completion corrupts every number downstream, and the user will
believe it because it came from their own tracker.

## natural-language logging

1. **log what happened, not what was planned.**
2. **preserve a useful description**, plus quantity, unit, category, and source when relevant.
3. **use the user's exact values.** "7.5 hours" is 7.5, not "about 7".
4. **if a missing detail materially changes the value, ask one focused question** — or ask
   permission to estimate. do not quietly average.
5. **every agent-derived value is `--estimated` and carries `--assumption`.** the api rejects
   an estimate without one.
6. **after a write, report**: the date, what was recorded, whether it was estimated, and the
   updated aggregate or progress.
7. **after corrections or batches, read the data back from the api** before reporting.
8. **never guess an id when deleting.** `obs` first, then `obs-delete <id>`.

## common operations

```bash
T=".claude/skills/life-tracker/scripts/tracker.py"

python3 $T today                                    # today's checklist
python3 $T complete --habit 3                       # explicit completion
python3 $T complete --habit 3 --subtask 7           # one step of a routine
python3 $T complete --habit 3 --state skipped --note "rest day"
python3 $T reopen --habit 3 --date 2026-08-10       # undo; the old state stays in the audit log

python3 $T habit-add --title "morning run" --schedule weekdays --config '{"days":[0,2,4]}' \
    --goal 2 --subtasks "warm up" "run" "stretch"
python3 $T habit-set 3 --set status=paused paused_from=2026-08-12
python3 $T trend --habit 3 --days 30

python3 $T metric-add --id sleep_hours --label sleep --type duration --unit hours \
    --aggregation mean --chart bar --missing unknown
python3 $T log --metric sleep_hours --value 7.5
python3 $T log --metric sleep_hours --value 7 --estimated --assumption "user said 'about seven'"
python3 $T series --metric sleep_hours --days 30

python3 $T obs --metric sleep_hours --limit 5      # read before correcting
python3 $T obs-correct 42 --set value_num=8
python3 $T obs-delete 42                           # soft delete; value kept in the audit log
```

## schedule types

| type | config | scheduled on |
| --- | --- | --- |
| `daily` | — | every day |
| `weekdays` | `{"days":[0,2,4]}` (0 = monday) | those weekdays |
| `interval` | `{"every_n_days":3,"anchor":"2026-08-01"}` | every n days from the anchor |
| `min_frequency` | `{"times":3,"period":"week"}` | no fixed days; measured per period |

a habit is not the same as a temporary checklist (use a task) or a project task (use
`task-add`). pausing, skipping, replacing and rescheduling never corrupt past completions.

## metric definitions

every metric declares `missing_semantics`, and that choice changes every average it produces:

| value | means | effect |
| --- | --- | --- |
| `unknown` | no measurement taken | excluded from aggregates |
| `zero` | absence genuinely means zero | missing days count as 0 |
| `not_applicable` | did not apply that day | excluded |
| `incomplete` | partially logged | excluded from averages, visible in coverage |

if you are unsure which applies, ask. picking `zero` for a metric that means `unknown` turns
"i did not weigh myself" into "i weighed nothing".

update a metric definition or target **only when the user explicitly asks**.

## reporting numbers

- always give coverage with an average: "7.4 h mean over 12 logged days of 30".
- never report a streak. report consistency over scheduled days, and recovery after a gap.
- never present a correlation as a cause. "you slept more on days you ran" is an observation;
  "running improved your sleep" is a claim you cannot support.
- never claim a habit caused a goal outcome.

## pitfalls

- logging an intention, a plan, or a reminder as a completion.
- letting "today" default to utc because the timezone was never set.
- inventing a quantity the user did not give, instead of asking one question.
- an estimate without a preserved assumption.
- deleting by a guessed id.
- reporting an average without saying how many observations are behind it.
- treating an unlogged day as a zero, or a paused day as a failure.
- creating a second metric that means the same as an existing one.

## verification checklist

- [ ] the completion came from an explicit user action, not from time passing
- [ ] the date used the user's timezone
- [ ] estimated values are marked and carry their assumption
- [ ] i read the data back after a correction or batch
- [ ] i reported the date, the record, and the updated aggregate
- [ ] coverage accompanies any average i quoted
- [ ] no streak, no causal claim, no invented number
