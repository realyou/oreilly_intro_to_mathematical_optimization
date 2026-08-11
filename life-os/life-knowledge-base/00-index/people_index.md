---
id: idx-people
type: index
record_status: current
updated: 2026-08-11
---

# people index

one row per person. the row is a pointer; the facts live in the person's entity note.

| id | name | relationship | note | last updated |
| --- | --- | --- | --- | --- |
| _none recorded_ | | | | |

## rules

- id is `per-` plus a stable slug, chosen once. renaming a person adds an `aliases` entry;
  it never changes the id.
- create an entity note when a person recurs, carries context worth retrieving, or is
  referenced by more than one record. a single passing mention stays in the event note.
- health providers, employers, and organizations use `org-` and belong in their own notes.
- do not record contact details, addresses, or identifiers for other people beyond what the
  user needs for retrieval. third parties did not consent to this knowledge base.
