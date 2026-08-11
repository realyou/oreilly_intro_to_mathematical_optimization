# schema

the contract every record in this knowledge base follows. markdown is authoritative;
everything derived from it (indexes, csv, the search manifest, the tracker's cached copies)
is rebuildable and never edited by hand.

## frontmatter fields

include **only applicable fields**. an empty field is noise, and a field filled with a guess
is a lie.

```yaml
---
id: evt-20260811-001          # required, stable, never reused
type: event                    # event | source | person | org | project | goal | idea | condition | medication | supplement | lab | decision | resource | metric
subtype: health                # health | nutrition | project | personal | finance | goal | learning | social | ...
record_status: current         # current | historical | resolved | uncertain | superseded
epistemic: self_report         # fact | self_report | observation | hypothesis | preference
occurred_at: 2026-08-11        # when it happened
date_precision: day            # day | month | year | approximate  (omit when precision is day)
valid_from: 2026-08-11         # when this became true
valid_to: null                 # when it stopped being true; null = still true
recorded_at: 2026-08-11        # when it entered the knowledge base
created: 2026-08-11
updated: 2026-08-11
people: [per-jane-doe]
projects: [prj-example]
source_ids: [src-20260811-001]
confidence: medium             # high | medium | low
verification: user_reported    # verified | user_reported | unverified
needs_verification: false
supersedes: []                 # ids this record replaces
aliases: []
tags: []
tracker_id: null               # link to the tracker row, when one exists
---
```

### field semantics that matter

- **`record_status`** — `current` is what is true now. `historical` happened and is over.
  `resolved` was an open thing that closed. `uncertain` is believed but unconfirmed.
  `superseded` was replaced; it stays on disk, readable, with the replacement in the new
  record's `supersedes`.
- **`epistemic`** — the difference between "the user told me their b12 is low"
  (`self_report`) and "the lab pdf says b12 = 180 pg/mL" (`fact` with a `source_ids` entry)
  is the whole point of this system. never upgrade one to the other without a source.
- **`occurred_at` vs `recorded_at`** — a lab drawn in march and mentioned in august has
  `occurred_at: 2026-03-xx` and `recorded_at: 2026-08-xx`. aggregations use `occurred_at`.
- **`date_precision`** — set it whenever the day is not actually known. `2024` with
  `date_precision: year` is honest; `2024-01-01` is fabricated.
- **`valid_from` / `valid_to`** — bitemporal pair for facts that change (address, job,
  medication dose). the old record keeps its window instead of being overwritten.

## id prefixes

| prefix | for | example |
| --- | --- | --- |
| `evt-` | dated event | `evt-20260811-001` |
| `src-` | source record | `src-20260811-001` |
| `sym-` | symptom | `sym-headache` |
| `cond-` | condition or diagnosis | `cond-hypothyroid` |
| `med-` | medication | `med-levothyroxine` |
| `sup-` | supplement | `sup-vitamin-d3` |
| `lab-` | laboratory result | `lab-20260311-cbc` |
| `per-` | person | `per-jane-doe` |
| `org-` | organization | `org-acme-clinic` |
| `prj-` | project | `prj-kitchen-remodel` |
| `dec-` | decision | `dec-20260811-001` |
| `goal-` | goal | `goal-run-10k` |
| `idea-` | idea not yet promoted | `idea-newsletter` |
| `res-` | curated external resource | `res-pyomo-docs` |

dated ids use `prefix-YYYYMMDD-NNN`, sequential within the day. entity ids use a stable
slug — chosen once, then never renamed (add an alias instead).

## record body

```markdown
# human-readable title

## summary
one paragraph. what a reader needs if they read nothing else.

## details
the specifics.

## evidence and provenance
what backs each claim: source ids, urls with access dates, or the explicit label
"user report", "observation", "preference", or "hypothesis".

## connections
links to related notes, by relative path and id.

## uncertainty and follow-up
what is not known, what would resolve it, and what to ask next.
```

sections that would be empty are omitted rather than filled with filler.

## source records

`90-sources/records/src-*.md`, one per source, each recording:

| field | meaning |
| --- | --- |
| origin | where it came from (clinic portal, bank export, book, url, the user) |
| author / provider | who produced it, when known |
| document_date | the date on the document |
| received_at | when the user obtained it |
| path or url | `90-sources/files/...` for originals, canonical url for web |
| accessed_at | for urls |
| extraction_status | `raw` / `partial` / `extracted` / `verified` |
| reliability | `primary` / `secondary` / `unverified` |

the original file is preserved byte-for-byte in `90-sources/files/`. extraction never
overwrites the original.

## metrics

a metric definition lives in the tracker (`metric_defs`) and declares:

`id`, `label`, `type` (`numeric` | `boolean` | `categorical` | `duration` | `count` |
`rating` | `text`), `unit`, valid range or options, `aggregation` (`mean` | `sum` | `last` |
`count` | `distribution` | `none`), `chart` (`line` | `bar` | `calendar` | `count` |
`distribution` | `categorical_history`), `privacy`, and **`missing_semantics`** — one of:

| value | meaning |
| --- | --- |
| `unknown` | no measurement was taken; excluded from every aggregate |
| `zero` | absence genuinely means zero (e.g. cigarettes smoked) |
| `not_applicable` | the metric did not apply that day |
| `incomplete` | partially logged; excluded from averages, visible in coverage |

these are four different states and are never collapsed into one.

## validation

`.claude/skills/life-knowledge-base/scripts/kb_validate.py` checks: frontmatter parses,
ids are unique and correctly prefixed, dates are ISO and internally consistent,
`supersedes`/`source_ids` point at records that exist, links resolve, csv headers match, and
no secret-shaped string was committed. it prints findings, never file contents of secrets.
