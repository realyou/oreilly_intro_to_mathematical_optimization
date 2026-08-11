---
id: med-slug
type: medication
record_status: current
epistemic: self_report | fact
dose: ""
schedule: ""
prescriber: null
reason: ""
started_at: YYYY-MM-DD
valid_from: YYYY-MM-DD
valid_to: null
source_ids: []
supersedes: []
tags: [health]
---

# medication name

## current
dose, schedule, reason, prescriber.

## history
a dose change creates a **new record** that supersedes this one. the old record keeps its
`valid_to` and stays readable. never overwrite a dose in place.

## evidence and provenance

## notes
adherence is tracked in the tracker as a metric or habit, not narrated here.
