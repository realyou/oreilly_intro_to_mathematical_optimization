# receiptsplit: JSON contracts

All money is integer cents (`*_cents`). Every file is a plain JSON object. The
engine never guesses: missing or inconsistent data is reported in `issues`,
not silently fixed.

## receipt.json (output of an extraction adapter, input to the engine)

```json
{
  "id": "rigi-2026-09-20",
  "merchant": "Rigi Gastrodouqan",
  "date": "2026-09-20",
  "currency": "GEL",
  "lines": [
    {"id": "l1", "name": "Mineral Water Borjomi", "qty": 2, "price_cents": 932,
     "raw": "2 Mineral Water Borjomi 9.32", "confidence": 0.95}
  ],
  "subtotal_cents": 13303,
  "tax_cents": 2395,
  "service_cents": 0,
  "discount_cents": 0,
  "total_cents": 15698,
  "source": {"image": "fixtures/receipts/rigi.jpg", "extractor": "claude-sample-v1"}
}
```

Rules:
- `price_cents` is the line total as printed (qty times unit price). A
  per-line discount is a line with a negative `price_cents`.
- `total_cents` is what the receipt says is due. The engine treats
  `total_cents - sum(lines)` as the receipt-level extras (tax, service,
  rounding, receipt-level discount) and spreads it proportionally over the
  lines. `tax_cents` etc. are informational and used only for validation:
  if `subtotal + tax + service - discount != total`, an issue is raised.
- `confidence` is optional, 0..1. Lines below the review threshold are
  flagged, never dropped.

## allocation.json (human decisions, input to the engine)

```json
{
  "receipt_id": "rigi-2026-09-20",
  "paid_by": "me",
  "card": {"currency": "EUR", "amount_cents": 5337},
  "lines": {
    "l1": {"target": "shared"},
    "l2": {"target": "personal:supi"},
    "l3": {"target": "daughter"},
    "l4": {"target": "unassigned"}
  }
}
```

Rules:
- `target` is one of `daughter`, `daily`, `shared`, `personal:<person>`,
  `unassigned`. Lines missing from `lines` are `unassigned`.
- `card` is the amount actually charged, authoritative. When absent, the
  receipt currency is used unchanged (rate 1). A `rate` may be given instead
  of `card` (`{"rate": 0.34}`) and then `card.amount_cents` is derived.
- `paid_by` is a person id from the policy.

## policy.json (who the people are, how each target is split)

```json
{
  "people": {"me": "Christian", "supi": "Supi"},
  "targets": {
    "daughter": {"label": "Daughter", "shares": {"me": 1, "supi": 1}},
    "daily":    {"label": "Daily Expenses", "shares": {"me": 1, "supi": 1}},
    "shared":   {"label": "Shared", "shares": {"me": 1, "supi": 1}},
    "personal:me":   {"label": "Christian only", "shares": {"me": 1}},
    "personal:supi": {"label": "Supi only", "shares": {"supi": 1}}
  },
  "notes": {"date_format": "%d %b %Y", "currency_symbols": {"USD": "$", "EUR": "€", "GBP": "£"}}
}
```

## allocation_result.json (output of the engine, one per batch of receipts)

```json
{
  "card_currency": "USD",
  "receipts": [{"id": "...", "merchant": "...", "date": "...", "receipt_currency": "IDR",
                "receipt_total_cents": 1234500, "card_total_cents": 4883, "implied_rate": 0.0039555,
                "lines": [{"id": "l1", "name": "...", "target": "daughter",
                           "receipt_cents": 50000, "receipt_gross_cents": 55000, "card_cents": 477}]}],
  "targets": {"daughter": {"card_cents": 855, "lines": [...]},
              "unassigned": {"card_cents": 2079, "lines": [...]}},
  "issues": [{"level": "error|warning", "receipt_id": "...", "line_id": "...", "message": "..."}]
}
```

Invariants (tested):
- per receipt: `sum(receipt_gross_cents) == receipt_total_cents` and
  `sum(card_cents) == card_total_cents`
- per batch: `sum over targets of card_cents == sum of card totals`
- per target: `sum(line card_cents) == target card_cents`
- rounding: largest remainder, deterministic (ties broken by line order)

## publish_request.json (one per target, what goes into Splitwise)

```json
{
  "target": "daughter",
  "description": "Daughter 06 Nov 2026",
  "currency": "USD",
  "cost_cents": 855,
  "paid_by": "me",
  "owed_cents": {"me": 428, "supi": 427},
  "notes": "Apotekku — 06 Nov 2026\n$4.77 Youvit ...\n----\nTotal: $8.55",
  "fingerprint": "sha256 of (target, card currency, cost, sorted line ids and cents)",
  "status": "draft"
}
```

`owed_cents` are the target's shares applied with largest remainder.
`fingerprint` is the duplicate key: the ledger refuses to publish the same
fingerprint twice. Without API access (Splitwise Pro required), publishing
means: print the request as a paste-ready sheet, the user enters it in the
Splitwise app, then marks it `published` with the Splitwise expense id or
a note in the ledger.
