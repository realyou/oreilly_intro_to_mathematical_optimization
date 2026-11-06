# Receipt Splitting → Splitwise: Status Assessment and Recommendation

Date: 6 November 2026 · Branch `claude/family-expense-splitting-6owct8` · Folder `family_split/`

This document answers the 6 November handover: what exists, where it falls short of the receipt-to-Splitwise workflow, which external options are worth using, and a prioritized backlog with a proposed division of work between Claude and ChatGPT/Codex. Nothing in the existing application was changed while writing it.

## 1. Baseline: what actually exists

**Correction to the handover's premise.** There is no local Mac application. What was built in September 2026 is a browser page published as a Claude Artifact ("Familienkasse") whose data lives in the Artifact's shared database on claude.ai, plus a Python settlement solver in this Git repository. It was designed for a different problem than the handover describes: a Splitwise-style family ledger (who paid, who owes whom, minimal transfers), not a pipeline that turns receipts into Splitwise expenses.

**Location and stack**

- `family_split/index.html` (854 lines): single-file app, vanilla JavaScript, no build step, no dependencies. Published at https://claude.ai/artifact/DvtkB46q3751SMsR9xX5qQ (version 2). Uses three claude.ai runtime capabilities: `db` (shared store), `user` (viewer identity), `sample` (asks Claude to read a receipt photo).
- `family_split/settle.py` (223 lines): minimum-transfer settlement, exact via subset DP and as a PuLP integer program; plus `split_items()`, a Python twin of the browser's itemized split.
- `family_split/test_settle.py`: property tests (DP optimal against brute force on 300 random cases, greedy counterexample, item split sums exactly). Passing.
- `family_split/README.md`: concept, data model, rounding rules.

**Features that work (verified in a headless browser in September, and by the Python tests)**

- Members by name, no accounts. Expenses with four split modes: equal, shares, exact, itemized.
- Itemized split: each line assigned to one or more people; the difference between receipt total and line sum (tax, service, rounding) is spread proportionally to each person's line subtotal; largest-remainder rounding so cents reconcile exactly.
- Multi-currency: each expense keeps its currency and a frozen rate; a field "charged on card" derives the effective rate from the actual card amount (added 23 September). Balances run in a base currency.
- Receipt photo → line items via Claude inside the page (schema: merchant, date, currency, items, subtotal, tax, tip, total).
- Review-before-save form with a reconciliation check (split sum must equal amount).
- Settlement with the provably minimal number of transfers.

**Usage status: none.** The shared database still has an empty member list and five Georgian restaurant receipts from 20 to 23 September, all without a payer. Nobody onboarded. Everything above is a prototype that has not been exercised by real use.

**Receipt extraction approach:** a prompt to Claude with the image, from inside the page, on the viewer's own Claude account. Thousands separators, discounts and Indonesian receipts have never been tested. The extraction is not portable: it only runs inside the claude.ai viewer.

**Splitwise integration: none.** No API client, no MCP, no notion of a target Splitwise group or of "Daughter / Daily / Personal / Unassigned" tags.

**Tests and technical debt**

- Zero automated tests for the JavaScript (the money math exists twice: JS and Python, only the Python side is tested).
- Negative line items (per-line discounts) are not handled by the item split; a receipt-level discount is, via the proportional remainder.
- Data sits in a claude.ai artifact database: not in Git, not on the Mac, not reachable by Codex.
- `sample` extraction output is accepted as-is; no confidence flags, no "needs review" state beyond the missing payer.

## 2. Gap analysis against the handover requirements

| Requirement | Status | Note |
|---|---|---|
| Upload one or many receipt photos from mobile | Partially implemented | One photo per expense, from the claude.ai page. No batch, no duplicate-upload detection. |
| Extract merchant, date, lines, discounts, service, tax, total | Implemented, not tested | Works on the Georgian samples by eye. Discount lines, IDR separators, multi-page receipts untested. |
| Assign lines to me / Supi / daughter / shared | Partially implemented | Lines go to people. There is no "target group" dimension (Daughter group vs Daily Expenses vs personal). |
| Unassigned items stay visible until resolved | Missing | Unassigned lines silently count as "everyone". |
| Convert at the actual card charge | Implemented, not tested | "Charged on card" field sets the effective rate. Not covered by tests; no second-level rounding to the card currency. |
| Consolidate several receipts into one expense per group | Missing | The model is one expense per receipt. |
| Notes in the exact itemized format | Missing | |
| Review before publication | Partially implemented | Review exists for the ledger entry, not for a Splitwise payload. |
| Create expenses via official Splitwise API | Missing | |
| Duplicate-safe publishing, remote ID recorded | Missing | |
| Deterministic cent rounding, exact reconciliation | Implemented and tested (Python), untested (JS) | Largest remainder, integer cents. |
| Restaurant mixed individual and shared lines | Implemented, not tested | |
| Regression fixtures from real receipts | Missing | Five Georgian receipts exist as data, not as test fixtures. The Nov 6 Apotekku/Pepito and the three Thalassa figures cannot be recomputed: the handover lists item names but not the original prices. |
| Provider-agnostic core | Missing | Extraction is Claude-only; the calculation logic is embedded in a browser page. |
| Local / portable deployment | Missing | Cloud artifact only. |

The honest summary: the **money math** (item split, proportional extras, exact cents, card-rate) is the one part of the existing app that maps directly onto the new requirements, and it already exists in Python. The **product shape** (shared family ledger, settlement) is not what the handover asks for.

## 3. External options, evaluated on evidence

### Official Splitwise API (source: splitwise/api-docs on GitHub, the repo that builds dev.splitwise.com)

- Auth: personal API key as `Authorization: Bearer`, or OAuth2. Registration at secure.splitwise.com/apps. Non-commercial, rate limits "lenient", 429 on excess, no numeric limits published.
- `POST /create_expense`: `cost` (string, 2 decimals), `description`, `details` (the notes), `date`, `currency_code`, `category_id`, `group_id`, and either `split_equally` or `users__N__user_id` / `paid_share` / `owed_share` as 2-decimal strings. Shares must total the cost; a 33.33 × 3 for 100.00 is rejected (community-reported, not in the spec).
- A 200 response does **not** mean success. Success only if the `errors` object is empty.
- **No idempotency key, no duplicate prevention of any kind.** A retried create after a timeout produces a second expense. Duplicate safety must be built client-side: write a local ledger entry before the call, verify with `get_expenses?group_id=&dated_after=` after it.
- Read-after-write: `get_expense/{id}`, `get_expenses` with `group_id`, `dated_after/before`, `updated_after`, `limit`, `offset`. `get_currencies` needs no auth; whether IDR is listed could not be verified from this network and must be checked with one call.
- Python client `splitwise` on PyPI: last release June 2023, effectively unmaintained. The API surface we need is two endpoints; a 100-line `requests` wrapper is lower risk than a stale dependency.
- Max length of `details` is undocumented. Must be tested with a long notes block before relying on it.

### MCP server option 1: svarun115/splitwise-mcp-server (TypeScript)

- 1 star, single author, 16 commits, last September 2026, no releases, no CI, one unit test file. README claims 26 tools; the code exports 9.
- Supports custom shares and `details`, which is what we need.
- Red flags: the `--http` mode listens on all interfaces with no authentication and trusts an `X-User-Id` header; a real access token was committed once and later removed; token-file path built from an unsanitized user id.
- Verdict: usable only over stdio on a trusted machine, and even then it adds nothing over calling the API directly from our own code.

### MCP server option 2: vishnujayvel/splitwise-mcp (Python)

- 0 stars, 7 commits in two days (December 2025), the only CI run failed, no activity since.
- Hard-coded to two people and one group; no free-form notes (`details` is always "Order #…"); no per-user shares.
- The advertised duplicate prevention is a SQLite reservation with a fuzzy word-overlap match; `create_expense` calls Splitwise before validating the reservation, so the guarantee does not hold.
- Verdict: not adoptable. The *idea* (reserve locally, then create, then confirm) is right and is cheap to implement properly ourselves.

### ShareTab (sw-carlos-cristobal/sharetab)

- 66 stars, MIT, 7 months old, very active single maintainer (auto-tagged builds, several per day), 134 open issues. Next.js 16, Prisma, PostgreSQL, all-in-one Docker image.
- The closest functional match for extraction: providers OpenAI, Claude, ChatGPT-OAuth, Ollama (local); extracts items with quantity, unit and total price, subtotal, tax, tip, currency, confidence; assigns lines per person with proportional tax and tip; guest claim links without accounts.
- Multi-currency: ECB rates via frankfurter.app for the expense date, with manual rate override (since 2 November 2026). An actual card amount can therefore be expressed as a manual rate, but balances are converted into the group currency, not kept per currency.
- No public API, no MCP, no Splitwise import or export, no CSV export; members need accounts. Assignment is per person, not per target group, and there is no cross-receipt consolidation.
- Verdict: a good **benchmark** for extraction quality and for how a mature item-assignment UI feels. Not a path to Splitwise, and adopting it would mean a second ledger beside Splitwise.

### Spliit (spliit-app/spliit)

- 3k stars, MIT, weekly releases, Next.js 16, PostgreSQL, node 24+.
- Receipt scan extracts only total, date, title and category. No line items, no item split. Splitwise import is a 2024 roadmap issue, not a feature. No API.
- Verdict: not relevant to line-item splitting. Mentioned only to close the question.

## 4. Strategies compared

| | A. Continue our app as is | A′. Continue, re-platformed around a Python core | B. Integrate an MCP server / open-source component | C. Run ShareTab as reference |
|---|---|---|---|---|
| Fits the workflow | No: ledger, not receipt → Splitwise | Yes | Partially (MCP = transport only) | Extraction + per-person assignment only |
| Security | Fine (claude.ai) | Fine (local, key via env/keychain) | Poor (both MCP servers) | OK, self-hosted |
| Maintenance burden | Low | Low: ~1k lines Python, two API endpoints | Depends on abandoned projects | Medium: Docker + Postgres, fast-moving upstream |
| Effort to first Splitwise publish | Large, and still Claude-bound | 3 to 5 focused sessions | Similar to A′ plus auditing foreign code | Zero for extraction, infinite for publishing |
| Portability / Codex-compatible | No (window.claude) | Yes: CLI + JSON files in Git | Partially | No |
| Long-term flexibility | Low | High: swap extractor, swap publisher | Low | Low |

**Recommendation: A′.** Keep what is proven (the Python money math and its tests, the extraction prompt and schema, the review-before-save idea), move the core into a small provider-agnostic Python package in this repository, and write the Splitwise publisher ourselves against the official API. Reject both MCP servers on evidence; if an MCP interface is wanted later, wrap our own core (one evening of work with the official MCP SDK). Run ShareTab once, in Docker on the Mac, purely to benchmark extraction on the same fixture receipts and to steal UI ideas (C as a side task, not a dependency). Keep the Familienkasse artifact as it is: it can later become one optional front end for the same JSON files, or be retired.

Two design decisions this implies:

- **Allocation is two-dimensional.** Every line gets a person set (who consumed it) **and** a target (Splitwise group "Daughter", "Daily Expenses", personal me / Supi, or Unassigned). Publishing aggregates by target; within a target the Splitwise shares follow that group's standard ratio (to be confirmed per group).
- **Rounding happens twice, both with largest remainder.** First the receipt-currency lines plus proportional extras are allocated to targets in receipt cents. Then the actual card charge is distributed across targets in card cents proportionally to those receipt-cent totals, and within each target across lines so the notes add up to the target total exactly. The card charge is authoritative; the implied rate is recorded for audit.

## 5. Backlog (prioritized, each with acceptance criteria)

1. **Core package `receiptsplit/` with JSON contracts.** Files: `receipt.json` (extraction output, keeps raw text per line and a confidence), `allocation.json` (person set + target per line, card charge), `publish_request.json` (one per target). Acceptance: schemas documented in `CONTRACTS.md`; `split_items()` moved in unchanged and its tests green.
2. **Allocation engine: two-level largest-remainder.** Acceptance: for every fixture, receipt lines sum to the receipt total; target totals sum to the card charge; per-line note amounts sum to the target total; discounts and tax counted exactly once; negative lines supported; property test on random receipts.
3. **Fixtures from real receipts.** The five Georgian receipts already in the database, plus Apotekku, Pepito and the three Thalassa bills once their photos (or line prices) are added to `fixtures/`. The ChatGPT figures become expected values only after the engine recomputes them and the user signs the numbers off. Acceptance: `pytest` runs them all.
4. **Notes renderer.** Exactly the handover format: merchant line with em dash and date, `$x.xx name` lines, `----`, `Total:`. Acceptance: golden-file tests against the two examples in the handover, byte-identical.
5. **Splitwise publisher, dry-run by default.** `requests`-based, API key from an environment variable or the macOS keychain, never in Git. Flow: write a pending row in a local SQLite ledger keyed by a deterministic hash of (target, date, card total, line hashes) → `create_expense` → treat non-empty `errors` as failure → `get_expense` read-back → store remote id. A second run with the same hash is refused. Acceptance: tests with a mocked API including timeout-then-retry producing exactly one expense; a live test against a dedicated "Test" group in Splitwise.
6. **Extraction adapters.** Interface `extract(image) -> receipt.json`; first adapter Claude (reusing the existing prompt), second adapter OpenAI (Codex's natural choice). Acceptance: both pass the same fixture set; IDR thousands separators and discount lines parsed; per-line confidence below threshold flags the receipt as needing review instead of guessing.
7. **CLI for the full loop on the Mac.** `receiptsplit ingest *.jpg`, `allocate`, `preview`, `publish --confirm`. Acceptance: the Nov 6 example runs end to end with manual tagging, producing two expenses in a test group.
8. **Mobile ingestion.** Simplest robust path: photograph with the phone and share to a folder that syncs to the Mac (iCloud, Drive), the CLI watches that folder. Alternatively keep the artifact page as the capture front end and have it write `receipt.json` into its database for the CLI to pull. Decide after 1 to 7.
9. **Deployment.** Local only until 7 is stable. Docker is optional (the stack is plain Python). A shared web host without persistent processes is unsuitable for the publisher; a small VPS or the Mac itself is enough. No unauthenticated write endpoint, ever.

## 6. Division of work with ChatGPT/Codex

Git is the only source of truth. Both agents work on branches in this repository, nothing merges without the fixture tests passing.

- **Claude:** items 1, 2, 4, 5 (contracts, engine, notes, publisher). These are the deterministic, test-heavy parts where one coherent author matters.
- **Codex:** item 6 (OpenAI extraction adapter) and item 7's CLI/UI, both against the contracts from item 1. Codex can start on the adapter immediately using the Georgian receipt photos, before the engine is finished, because the contract is just JSON.
- **Both:** add fixtures; each extraction adapter is scored on the same fixtures, and the engine tests are the shared regression suite.
- **Benchmark side task (either):** run ShareTab in Docker, feed it the fixture receipts, record extraction accuracy and the assignment UX in `docs/sharetab-benchmark.md`.
- **Coordination rules:** secrets only in environment variables or the keychain, a `.env.example` in Git; the publisher refuses to run without `--confirm` and without the ledger file; only one machine holds the real API key during development, the other uses dry-run; a dedicated Splitwise "Test" group for live checks; schema changes go through a PR that updates `CONTRACTS.md` and all fixtures.

## 7. Open questions for the user

1. The Splitwise group memberships and default ratios for "Daughter" and "Daily Expenses" (50/50 between you and Supi?), and how personal allocations should be published (not at all, or as an expense with 100 percent owed by the other person?).
2. Photos or line prices for the Apotekku, Pepito and Thalassa receipts, so they can become fixtures. Without them the earlier allocation figures cannot be validated.
3. Whether the Familienkasse artifact should stay alive as the phone-side capture front end, or be retired in favour of a synced folder.
