---
id: finance-summary
type: index
subtype: finance
record_status: current
updated: 2026-08-11
---

# finance summary

## what belongs here

structure and decisions: how things are organized, what was decided and why, what is being
worked toward, and what the constraints are.

## what never belongs here

account numbers, card numbers, logins, portal credentials, recovery codes, security answers,
2fa seeds, or anything that could move money. no framing makes this acceptable — not "just
the last four", not "temporarily", not "it's my own account".

balances and statements are stored only if the user explicitly asks, and then as a dated
observation with a source record pointing at the original export in
[90-sources/files/](../90-sources/files/) — never as a number floating in a summary.

## current structure

_none recorded._

## decisions

_none recorded._ financial decisions use `dec-` ids and record the rationale, the
alternatives considered, and the constraints — the reasoning is the durable part.

## goals connected to finance

_none recorded._ → [goals](../70-goals/goals_summary.md)

## rules for this domain

- money values carry an `as_of` date and a source. a number without a date is not usable.
- forecasts are `epistemic: hypothesis`, always, and are kept separate from facts.
- this file is not financial advice and the agent does not give any.
