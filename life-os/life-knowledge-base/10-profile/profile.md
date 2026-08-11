---
id: per-user
type: person
record_status: current
epistemic: self_report
created: 2026-08-11
updated: 2026-08-11
aliases: []
tags: [profile]
---

# profile

stable facts about the user. things that change often do not belong here — they belong in
dated records, with this file linking to the current one.

## onboarding — unanswered

**do not guess any of these.** ask all four in one turn the first time the user shares
personal context, then fill them in here and in `agent_rules.md` §2, then delete this
section and log the change in `95-system/changelog.md`.

1. **name and timezone** — what should i call you, and which timezone should dates use?
   - answer: _unanswered_
2. **privacy exclusions** — what must never be stored here, or only stored generalized?
   - answer: _unanswered_ (the hard floor already applies: no credentials, keys, seed
     phrases, recovery codes, payment authentication, or portal logins, ever)
3. **priority domain** — which life domain matters most right now?
   - answer: _unanswered_
4. **first ingest** — which documents, links, exports, or records should be ingested first?
   - answer: _unanswered_

## identity

| field | value | epistemic | source |
| --- | --- | --- | --- |
| name | _unknown_ | — | — |
| preferred address | _unknown_ | — | — |
| timezone | _unknown_ | — | — |
| location | _unknown_ | — | — |

## stable facts

_none recorded._ add rows only for facts that are durable and that you would otherwise ask
about repeatedly. each row carries an epistemic label and a source.

## preferences

_none recorded._ preferences are `epistemic: preference` — they are true because the user
said so, and they change; date them.

## constraints and context

_none recorded._

## do not store

- credentials, passwords, cookies, recovery codes, api keys, seed phrases, payment
  authentication, portal logins, 2fa codes — never, under any framing.
- anything the user names in onboarding question 2.
