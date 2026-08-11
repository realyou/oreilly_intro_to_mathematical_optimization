# life OS

a private, file-based knowledge base and a synchronized life tracker, so an agent can be
useful about your life without you re-explaining it every session.

four connected layers, one set of conventions:

| layer | where | what it is |
| --- | --- | --- |
| **1 · knowledge base** | `life-knowledge-base/` | portable markdown. the detailed source of truth. |
| **2 · persistent memory** | `../CLAUDE.md` | a pointer to layer 1. routing only, never a database. |
| **3 · agent skills** | `../.claude/skills/` | six reusable skills for capture, retrieval, correction, planning, review. |
| **4 · life tracker** | `tracker/` | today's checklist, habits, goals, projects, dated metrics. |

all four share the same dates, privacy rules, id scheme, and source hierarchy.

## start here

```bash
# 1. read the rules that govern everything
cat life-knowledge-base/agent_rules.md

# 2. start the tracker
python3 tracker/server.py                    # http://127.0.0.1:8787

# 3. check it all still holds together
./tests/run_tests.sh
```

**onboarding is not done.** the four foundation questions in
`life-knowledge-base/10-profile/profile.md` are unanswered: what to call you, your timezone,
what must never be stored, and which domain matters most. nothing about you has been guessed
or invented — the system asks before it captures.

## the principles it actually enforces

these are not aspirations in a readme; each one is implemented and tested.

- **files are the truth.** memory holds the path and stable preferences, nothing else.
  chat history is context, never proof of current state.
- **nothing is invented to fill a field.** empty stays empty; `unknown` is a valid answer.
- **every claim is labelled** — fact, self-report, observation, preference, or hypothesis —
  and consequential ones cite a source.
- **uncertainty and conflict are preserved**, not silently resolved. conflicts land in
  `00-index/open_questions.md`.
- **corrections override summaries; superseded records stay traceable.** nothing is deleted.
- **exact dates when known, explicit precision when not.** "a couple of years ago" becomes
  `2024` with `date_precision: year`, never an invented day.
- **summaries answer "what is true now?"; dated records answer "what happened, when?"**
- **markdown is authoritative**; indexes, csv, charts, sqlite, and search manifests are
  rebuildable derivatives.
- **completion is recorded only from an explicit action** — never because a day ended or a
  reminder fired.
- **missing means four different things** (`unknown`, `zero`, `not_applicable`,
  `incomplete`) and every metric declares which.
- **progress comes from criteria, milestones, or explicit scope** — never from elapsed time
  or task volume. a goal with neither reports "qualitative", not a number.
- **no streaks, no causal claims** from co-moving personal data.
- **capture is cheap.** a routine update is one targeted write and one short acknowledgement.
- **no credentials, ever** — no passwords, keys, seed phrases, recovery codes, or payment
  authentication, under any framing.
- **nothing leaves the machine** without explicit approval for that specific destination.

## layout

```text
life-os/
├── life-knowledge-base/     portable markdown; agent_rules.md governs everything
│   ├── 00-index/            master index, people, projects, sources, open questions
│   ├── 01-inbox/            unprocessed capture
│   ├── 10-profile/          who the user is, stable facts, onboarding answers
│   ├── 20-timeline/         timeline.md + dated events under events/YYYY/
│   ├── 30-health/           summary + conditions, medications, procedures, tests, logs
│   ├── 40-nutrition/        summary + logs
│   ├── 50-projects/         summary + one note per durable project
│   ├── 60-finance/          summary (never account numbers or credentials)
│   ├── 70-goals/            summary + one note per goal
│   ├── 75-ideas/            index + one note per idea
│   ├── 80-interests/        interests summary
│   ├── 85-resources/        curated external resources
│   ├── 90-sources/          originals in files/, one source record each in records/
│   └── 95-system/           schema, changelog, intake, backups, templates
├── tracker/                 stdlib python + sqlite; four views, authenticated api
└── tests/                   90 tests over semantics, auth boundary, and the validator
```

## the skills

| skill | use when |
| --- | --- |
| `life-knowledge-base` | capture, retrieve, or correct personal context |
| `life-tracker` | log a completion or a metric; read today; read a trend |
| `goal-planning` | turn an ambition into criteria, milestones, habits, next action |
| `project-context` | create or load project state, decisions, blockers, next action |
| `life-review` | daily, weekly, monthly, quarterly reviews |
| `resource-library` | save and retrieve urls and tools, read-before-summarizing |

## tests

```bash
./tests/run_tests.sh
```

90 tests, no dependencies, no network. they cover the things that would make the system lie:
habit scheduling and pauses, skipped-vs-missed, the four missing-value semantics, progress
basis, timezone refusal, the browser-versus-agent write boundary, csrf, path traversal, soft
deletion and audit history, and the knowledge-base validator's ability to actually catch a bad
date, a duplicate id, a dangling reference, a broken link, and a committed secret.

## privacy

everything is local: sqlite on disk, markdown in a directory, a server bound to `127.0.0.1`.
no cloud, no cdn, no analytics, no external requests from the web app. the tracker token and
database are gitignored. secrets are never written, and the validator fails the build if one
appears.
