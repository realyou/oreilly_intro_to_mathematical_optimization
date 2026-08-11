# persistent memory — routing only

## life knowledge base

**absolute path:** `/home/user/oreilly_intro_to_mathematical_optimization/life-os/life-knowledge-base`

that directory is the **detailed source of truth** about the user. this file is a pointer to
it, not a copy of it.

**before answering any personal question, or storing any substantial personal context:**

1. read `life-os/life-knowledge-base/agent_rules.md` — it holds the user's own rules and
   outranks this file.
2. search the knowledge-base files. do not answer from memory or from chat history.
3. cite note paths, ids, and dates when accuracy matters.

**related pieces:**

- tracker (habits, goals, projects, dated metrics): `life-os/tracker/` — start with
  `python3 life-os/tracker/server.py`
- skills: `.claude/skills/` — `life-knowledge-base`, `life-tracker`, `goal-planning`,
  `project-context`, `life-review`, `resource-library`
- overview: `life-os/README.md`

**standing rules:**

- files are authoritative; this memory is routing only. it never holds histories, logs, or
  documents.
- never invent facts to fill an empty field.
- never store credentials, keys, seed phrases, recovery codes, or payment authentication.
- do not send knowledge-base content to third parties without explicit approval.

**onboarding is incomplete.** the four foundation questions in
`life-os/life-knowledge-base/10-profile/profile.md` are unanswered — the user's name,
timezone, privacy exclusions, and priority domain are unknown. ask them before capturing
personal context, and do not guess any of them.

---

## about this repository

the repository itself is O'Reilly *Intro to Mathematical Optimization* course material
(`code/`, `slides/`, `demos/`, `videos/`). the life OS in `life-os/` is a separate,
self-contained system that shares the repo but not the subject matter.
