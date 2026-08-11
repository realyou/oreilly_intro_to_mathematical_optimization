---
id: idx-projects
type: index
record_status: current
updated: 2026-08-11
---

# projects index

| id | project | status | phase | note | tracker_id | last updated |
| --- | --- | --- | --- | --- | --- | --- |
| _none recorded_ | | | | | | |

## rules

- status is one of `active`, `blocked`, `paused`, `completed`, `abandoned`.
- this index carries no facts the project note does not already carry — it is a routing
  table. if you find yourself updating a detail here and not in the note, stop.
- a project with a tracker row carries its `tracker_id`; the tracker row carries `kb_path`
  back to the note. the prose lives only in the note.
- completed and abandoned projects stay listed. history is not deleted.
