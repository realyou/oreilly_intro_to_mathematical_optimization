---
id: idx-sources
type: index
record_status: current
updated: 2026-08-11
---

# sources index

every source record, with enough detail to decide whether to reopen the original.

| id | origin | author/provider | document date | received | reliability | extraction | record |
| --- | --- | --- | --- | --- | --- | --- | --- |
| _none recorded_ | | | | | | | |

## rules

- `reliability`: `primary` (the thing itself — a lab report, a bank export, a contract),
  `secondary` (someone describing the thing), `unverified` (unknown provenance).
- `extraction`: `raw` (stored, not read), `partial`, `extracted`, `verified` (extraction
  checked against the original).
- originals are preserved byte-for-byte in `../90-sources/files/`. extraction never
  overwrites an original.
- a claim that matters cites a source id from this table, or it carries an epistemic label
  saying it is a user report, observation, preference, or hypothesis.
