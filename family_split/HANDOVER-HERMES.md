# Handover to Hermes Desktop: Receipt Splitting Coordinator

Date: 6 November 2026 · Repository `realyou/oreilly_intro_to_mathematical_optimization`, branch `claude/family-expense-splitting-6owct8`, folder `family_split/` · Owner: Christian · Shares with: Supi

## 0. Your role, Hermes

You run on Christian's Mac and coordinate three parties: **Christian** (decides, reviews, enters into Splitwise), **Claude Code** (cloud sessions; owns the calculation core, the publisher and the Google Drive ingestion), and **ChatGPT/Codex** (owns the receipt extraction adapter and the dashboard). You are the only process that writes the local ledger and the only one that moves files in the Drive folder. You never publish anything to Splitwise: there is no API access (Splitwise Pro would be required), so publishing means Christian types the entry from a sheet you produce. Nothing leaves "draft" without Christian's explicit approval in the chat.

Assumptions about you, to confirm on first run: shell and file access on the Mac, Python 3.10+ available, the Google Drive desktop app syncing the shared folder to a local path, API keys for OpenAI and/or Anthropic configured in your own settings (never in the repo), the ability to run a scheduled task.

## 1. What exists and works today

- `family_split/receiptsplit/`: pure-Python package, no dependencies.
  - `engine.py`: receipt lines plus proportional extras (tax, service, rounding, discount) to targets, then the actual card charge to lines, largest-remainder rounding, exact to the cent. Validation returns `issues`, never guesses.
  - `notes.py`: itemized notes in the agreed format (merchant line with em dash and date, `$x.xx name` lines, `----`, `Total:`).
  - `publish.py`: one request per target with owed shares and a fingerprint. `ledger.py`: local JSON ledger that refuses fingerprints it has seen.
  - `__main__.py`: CLI `preview`, `publish`, `done`.
- `family_split/CONTRACTS.md`: the JSON shapes every party must respect. Read it before writing any adapter.
- `family_split/fixtures/`: policy, five Georgian restaurant receipts (Sep 2026) and the 6 Nov Apotekku/Pepito batch; the latter reproduces the handover figures (8.55 / 19.49 / 20.79, total 48.83) and the notes byte for byte.
- `family_split/tests/test_receiptsplit.py`: 13 tests, all green. Run with `cd family_split && python3 tests/test_receiptsplit.py` or `python3 -m pytest`.
- `family_split/index.html`: the September "Familienkasse" page, a shared family ledger on claude.ai. Untouched, unused, optional. Not part of this pipeline.
- `family_split/ASSESSMENT-2026-11-06.md`: why these decisions were taken (Splitwise API, the two MCP servers, ShareTab, Spliit).

Not yet built: the extraction adapter (photo to `receipt.json`), the Drive watcher, the assignment step as a UI (today it is a JSON file edited by hand), the dashboard.

## 2. Folder layout

Google Drive, shared folder `splits`: https://drive.google.com/drive/folders/1wuO9obOnSeU_zNKYzrZsSgSj4KMC8oNV, owned by the family account familyneuwirthmiller@gmail.com (good: Supi and Christian both use it, and the quota is that account's). The Google account connected to Claude is cccmiller@gmail.com; on 6 Nov it could read the folder through the public link but not write or move (viewer rights). For Claude to move photos and drop JSON into `out/`, Christian shares the folder with cccmiller@gmail.com as editor and switches the public link off again: receipts are personal data and should not be reachable by anyone with the link. Christian creates the subfolders below inside `splits` (or Claude does once it has editor rights):

```
splits/
  inbox/                 new photos, any name, from either phone
  processing/            a photo that an adapter is currently working on
  needs-review/          extraction unsure, or lines unassigned for more than a day
  processed/2026-11/     photo moved here after its ledger entry is marked done
  out/2026-11-06/        receipt.json, allocation.json, result.json, sheet.txt per batch
  policy.json            people and target share rules (copy of fixtures/policy.json)
  dashboard/             see section 6
```

On the Mac: the repo clone, plus `family_split/data/ledger.json` (git-ignored, personal data, backed up by copying it into `splits/out/` daily).

## 3. The pipeline, step by step

1. **Ingest.** On schedule (every evening) or on request, list `splits/inbox`. For each new photo compute a SHA-256 of the file; if the hash is already in `data/seen.json`, move the photo to `processed/duplicates/` and stop. Otherwise move it to `processing/`.
2. **Extract.** Call the extraction adapter (section 4) to produce `receipt.json`. Required: merchant, date, currency, lines with `price_cents`, `total_cents`; per-line `confidence`. Indonesian thousands separators (`15.000` is fifteen thousand) and discount lines (negative) must be handled by the adapter, not by the engine. If any required field is missing or the printed total does not match the lines plus extras within what the receipt itself states, move the photo to `needs-review/` and tell Christian what is unclear, with the raw line text. Never invent a price.
3. **Assign.** Produce a draft `allocation.json`: `paid_by`, `card` (currency and amount actually charged; ask Christian, he reads it from the bank app or card notification), and a target per line. Suggest targets from history (`data/suggestions.json`, a map from normalized item name to the target Christian chose last time) but mark every suggestion as a suggestion. Lines with no history stay `unassigned`. Show Christian the list; he confirms or corrects in chat; only then write the file.
4. **Preview.** Run `python3 -m receiptsplit preview --policy splits/policy.json --date <batch date> receipt.json:allocation.json [...]`. Show the sheet and every issue. Unassigned lines appear as a `BLOCKED` block and must be resolved or explicitly parked by Christian.
5. **Publish (draft).** On Christian's "go": run the same command with `publish --ledger data/ledger.json`. Each target becomes a draft with a fingerprint. A fingerprint that already exists is reported as duplicate and not recorded again.
6. **Enter in Splitwise.** Christian types each draft into the Splitwise app (description, amount, currency, paid by, split, notes pasted). Or, if he decides to drop Splitwise, this step is skipped and the ledger is the record.
7. **Done.** Christian says which entries are entered. Run `python3 -m receiptsplit done --ledger data/ledger.json <fingerprint> "<Splitwise reference or note>"`. Then move the photos of that batch from `processing/` to `processed/YYYY-MM/`, copy the batch's JSON and sheet to `out/<batch date>/`, update `suggestions.json` with the confirmed targets, and refresh the dashboard.

Restaurant bills follow the same steps; the targets are then mostly `personal:me`, `personal:supi` and `shared`.

## 4. Extraction adapter (owner: ChatGPT/Codex)

Contract: a command `extract <image> > receipt.json` (or a Python function `extract(path) -> dict`) that returns the `receipt.json` shape from `CONTRACTS.md`. First implementation: OpenAI vision with structured output; a second one with Claude is welcome. Acceptance:

- All seven fixture receipts produce the same line prices and totals as the fixture JSON (the Georgian photos are in the Claude session uploads and must be added to `fixtures/receipts/*.jpg` by Christian; the Apotekku and Pepito photos too, when available).
- Indonesian separators parsed; a per-line discount comes back negative; a service charge or tax line is reported in `service_cents` / `tax_cents`, not as an item.
- `confidence` is populated; anything below 0.6 is flagged by the engine automatically.
- No network call other than the model API; the image never leaves the Mac except to the model provider Christian chose.

## 5. Task board

| # | Task | Owner | Done when |
|---|---|---|---|
| 1 | `splits` exists on the family account. Create the subfolders, share with cccmiller@gmail.com as editor, turn the public link off, install Drive desktop sync on the Mac (family account), note the local path | Christian | Hermes can list `inbox` from the shell |
| 2 | Copy the receipt photos (5 Georgian, Apotekku, Pepito, 3 Thalassa) into `fixtures/receipts/` and the real IDR line prices into the two Nov fixtures | Christian | fixtures reflect the real receipts |
| 3 | Extraction adapter per section 4 | Codex | adapter passes the fixture comparison |
| 4 | Ingest/assign/publish runbook as a Hermes skill, with the duplicate hash check and `suggestions.json` | Hermes (with Claude for CLI changes) | one real batch processed end to end with Christian's approval |
| 5 | `assign` helper in the CLI: takes receipt.json plus a short text like `l1 daughter, l2 daily, rest shared` and writes allocation.json | Claude | tests added, used by task 4 |
| 6 | Dashboard (section 6) | Codex | Supi can open it on her phone and see balances and the last batches |
| 7 | Decide Splitwise vs own ledger only | Christian | decision recorded in this file |
| 8 | Thalassa and 17 Oct restaurant fixtures as regression tests, after the engine recomputes them and Christian signs off the numbers | Claude | tests green |

## 6. Dashboard options

- **Google Sheet `splits/dashboard/Ledger`** (recommended first). A sheet with one row per ledger entry and one per line, refreshed by Hermes after every batch. Works on both phones, needs no hosting, no accounts beyond Google.
- **Static HTML export** into `splits/dashboard/index.html`: renders fine when opened from the Mac's synced folder; on a phone Drive only previews it, so it is a desktop convenience, not a phone dashboard.
- **vHost**: a shared web host with PHP and MySQL is enough for a read-only dashboard page that reads a JSON or MySQL table Hermes uploads after each batch. It is not suitable for the pipeline itself (no persistent processes, no place for API keys you would trust). Needs to be confirmed what the host offers before anyone builds on it. Any page there must sit behind a login; nothing financial is public.

## 7. Rules for everyone

- Secrets only in Hermes' own configuration or the macOS keychain; `.env.example` in Git, never `.env`. The repo is public-readable on GitHub: no photos, no ledger, no real names beyond first names in `policy.json`.
- Git is the source of truth. Codex and Claude work on their own branches off `claude/family-expense-splitting-6owct8`; a change to `CONTRACTS.md` must update all fixtures and tests in the same commit; nothing merges with red tests.
- The ledger has one writer: Hermes on the Mac. Claude Code sessions in the cloud never touch `data/`.
- Every publish needs Christian's approval in chat; `preview` is free, `publish` is not.
- A failing test is never deleted or skipped; an extraction that does not reconcile goes to `needs-review`, never into a batch.

## 8. Decisions pending (Christian)

1. Keep Splitwise as the shared record (manual entry from the sheet) or let the ledger plus dashboard replace it?
2. Dashboard: Sheet first, vHost later?
3. Who pays usually? If the card is always Christian's, `paid_by: me` becomes the default and Supi's purchases are the exception.

## 9. Quick commands

```
cd family_split
python3 tests/test_receiptsplit.py                                # 13 tests
python3 -m receiptsplit preview --policy fixtures/policy.json --date 2026-11-06 \
  fixtures/receipts/apotekku-2026-11-06.json:fixtures/allocations/apotekku-2026-11-06.json \
  fixtures/receipts/pepito-2026-11-06.json:fixtures/allocations/pepito-2026-11-06.json
python3 -m receiptsplit publish --ledger data/ledger.json --policy fixtures/policy.json --date 2026-11-06 <same pairs>
python3 -m receiptsplit done --ledger data/ledger.json <fingerprint> "entered in Splitwise"
```
