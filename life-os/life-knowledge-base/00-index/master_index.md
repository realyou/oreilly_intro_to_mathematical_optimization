---
id: idx-master
type: index
record_status: current
updated: 2026-08-11
---

# master index

every canonical summary in this knowledge base, linked once. this file is a map, not a
store — it holds no facts of its own.

## entry points

| domain | canonical summary | detail lives in |
| --- | --- | --- |
| profile | [profile](../10-profile/profile.md) | — |
| timeline | [timeline](../20-timeline/timeline.md) | [events/](../20-timeline/events/) |
| health | [health_summary](../30-health/health_summary.md) | [conditions/](../30-health/conditions/) · [medications/](../30-health/medications/) · [procedures/](../30-health/procedures/) · [tests/](../30-health/tests/) · [logs/](../30-health/logs/) |
| nutrition | [nutrition_summary](../40-nutrition/nutrition_summary.md) | [logs/](../40-nutrition/logs/) |
| projects | [projects_summary](../50-projects/projects_summary.md) | [projects/](../50-projects/projects/) |
| finance | [finance_summary](../60-finance/finance_summary.md) | — |
| goals | [goals_summary](../70-goals/goals_summary.md) | [goals/](../70-goals/goals/) |
| ideas | [ideas_index](../75-ideas/ideas_index.md) | [ideas/](../75-ideas/ideas/) |
| interests | [interests_summary](../80-interests/interests_summary.md) | — |
| resources | [resources](../85-resources/resources.md) | — |
| sources | [sources_index](sources_index.md) | [records/](../90-sources/records/) · [files/](../90-sources/files/) |

## secondary indexes

- [people_index](people_index.md) — one row per person, linking to their entity note
- [projects_index](projects_index.md) — project ids, status, and note paths
- [sources_index](sources_index.md) — source ids, origin, reliability
- [open_questions](open_questions.md) — unresolved questions and recorded conflicts

## system

- [agent_rules](../agent_rules.md) — read first, always
- [schema](../95-system/schema.md) — fields, id prefixes, record shape
- [changelog](../95-system/changelog.md) — structural and high-value context changes
- [intake](../95-system/intake.md) — how new material enters
- [backups](../95-system/backups.md) — what a safe backup is
- [templates/](../95-system/templates/) — record templates

## state

the knowledge base is initialized and empty of personal content. onboarding questions in
[profile](../10-profile/profile.md) are unanswered; see `agent_rules.md` §0.
