---
id: changelog
type: index
record_status: current
updated: 2026-08-11
---

# changelog

structural changes and high-value context changes. not a diff log — git already does that.
this records decisions about *how the knowledge base itself works*, so a future agent knows
why the structure looks the way it does.

## what to append here

- new or removed directories, domains, or conventions
- schema changes
- privacy rule changes
- a correction that overturned something previously treated as settled
- an ingestion that materially expanded what is known

## what not to append

routine capture. logging every event note here would make it a second, worse timeline.

---

## 2026-08-11 — system initialized

- created the knowledge-base structure, schema, agent rules, and templates.
- created the tracker (`../../tracker/`) and the six agent skills
  (`../../../.claude/skills/`).
- no personal content captured. the four onboarding questions in
  `../10-profile/profile.md` are unanswered and gate personal capture (`agent_rules.md` §0).
