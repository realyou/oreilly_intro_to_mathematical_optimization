# life tracker

a private life operating system: today's checklist, goals, projects, and a read-only data
dashboard. python standard library and sqlite — no pip install, no build step, no external
service. the data never leaves the machine.

## run

```bash
cd life-os/tracker
python3 server.py                 # http://127.0.0.1:8787
```

on first run it generates `.token` (mode 0600, gitignored) and creates `life_tracker.db`.
open the url, paste the token once, and the browser keeps a session cookie.

```bash
python3 server.py --port 9000 --db /path/to/life_tracker.db
LIFE_TRACKER_TOKEN=... python3 server.py     # token from the environment instead
```

it binds to `127.0.0.1` by default. this is personal data — leave it there unless you have a
specific reason and know what you are exposing.

to see the interface working without inventing anything about yourself:

```bash
python3 demo_seed.py --db /tmp/demo.db      # fictional data, clearly labelled
python3 server.py --db /tmp/demo.db --port 8788
```

## the two identities

| identity | how | may do |
| --- | --- | --- |
| **agent** | `Authorization: Bearer <token>` | everything |
| **browser** | session cookie after sign-in | read everything; complete and reopen habits and tasks |

that split is the design. you tick things off in the browser; the agent creates goals,
restructures projects, defines metrics, logs observations, and makes corrections — in
conversation, in natural language. the `data` view has no form inputs and no delete controls,
and the server rejects those writes from a browser session even if the page were modified.

## views

- **today** — one focused vertical list for a single day, with previous/next navigation.
  habits, their subtasks, due goal actions, and project next actions. each row shows which
  goal or project it supports. completed items collapse into a section at the bottom.
- **goals** — grouped by life area: outcome, definition of done, status, target date, next
  review, success criteria, milestones, supporting projects and habits, next actions.
- **projects** — status, phase, owner, deadline, blockers, next action, expandable milestones
  and task checklists, and a health label that always shows its reasons.
- **data** — read-only. one chart at a time, chosen by the metric's own semantics, with
  7/30/90/365 ranges, coverage counts under every average, and estimated values marked.

refreshes on window focus and polls every 60 seconds, so writes the agent makes appear
without a reload.

## the semantics that make the numbers honest

- **completion is recorded only from an explicit action.** no endpoint marks anything done
  because a day ended or a reminder fired.
- **four missing-value states, never collapsed:** `unknown`, `zero`, `not_applicable`,
  `incomplete`. every metric declares which one applies, and that choice changes its average.
- **habit consistency divides by scheduled days.** unscheduled days, paused days, and
  explicitly skipped days are not in the denominator. minimum-frequency habits are measured
  per period, not per day.
- **no streaks.** consistency and recovery are reported instead; a streak punishes one missed
  day and hides everything that happened after it.
- **goal progress comes from success criteria, else milestones, else nothing** — a goal with
  neither reports `qualitative`, not an invented percentage.
- **project progress comes from milestones or task scope**, never elapsed time. health is a
  label with its reasons attached.
- **nothing is destroyed.** deletes are soft, corrections keep the previous value, and every
  write lands in an append-only audit log.
- **pausing or abandoning a goal or project requires a reason**, enforced by the api.
- **"today" requires a configured timezone.** until one is set the api returns 409 rather than
  guessing utc and filing a completion on the wrong day.

## api

all endpoints under `/api`. `GET /api/health` is unauthenticated; everything else needs an
identity.

| method | path | notes |
| --- | --- | --- |
| POST/DELETE | `/api/session` | browser sign-in and sign-out |
| GET/PATCH | `/api/settings` | timezone, name, kb path |
| GET | `/api/today?date=` | dated checklist |
| POST | `/api/habits/{id}/complete` · `/reopen` | `{date, subtask_id?, state?}`; browser-allowed |
| GET/POST | `/api/habits` · PATCH `/api/habits/{id}` | schedules, pauses, subtasks |
| GET | `/api/habits/{id}/trend?days=` | consistency over scheduled days |
| GET/POST | `/api/goals` · GET/PATCH `/api/goals/{id}` | |
| POST | `/api/goals/{id}/criteria` · PATCH `/api/criteria/{id}` | |
| POST | `/api/milestones` · PATCH `/api/milestones/{id}` | |
| GET/POST | `/api/projects` · PATCH `/api/projects/{id}` | |
| POST | `/api/tasks` · PATCH `/api/tasks/{id}` · `/complete` · `/reopen` | toggles browser-allowed |
| GET/POST | `/api/metrics` · PATCH `/api/metrics/{id}` | definitions and semantics |
| GET | `/api/metrics/{id}/series?days=&end=` | points, aggregate, coverage |
| GET/POST | `/api/observations` · PATCH/DELETE `/api/observations/{id}` | delete is soft |
| POST | `/api/events` · `/api/links` | dated events, cross-entity links |
| GET | `/api/data/summary?days=` | dashboard payload |
| GET | `/api/audit?limit=` | append-only write history |

the agent talks to this through `.claude/skills/life-tracker/scripts/tracker.py`, which wraps
every call above.

## security

- token compared with `hmac.compare_digest`; never logged, never sent to the browser.
- session cookie is `HttpOnly; SameSite=Strict`; browser writes additionally require an
  `X-Requested-With` header.
- static files are served from `static/` only, with a strict content-security-policy and no
  external requests — no cdn, no fonts, no analytics.
- request logs contain method, path and status. never query strings, bodies, or cookies.
- `.token` and `*.db` are gitignored.

## files

| file | what |
| --- | --- |
| `db.py` | schema, and every rule about what a number means |
| `server.py` | routing and auth, and nothing else |
| `static/` | the four views |
| `demo_seed.py` | fictional demo data, into a separate db, to see the ui working |
