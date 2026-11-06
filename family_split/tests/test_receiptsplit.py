"""Tests for the receiptsplit engine, notes and publishing.

Run: cd family_split && python -m pytest -q      (or: python tests/test_receiptsplit.py)
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from receiptsplit import Allocation, Policy, Receipt, allocate, build_publish_requests, distribute, render_notes  # noqa: E402
from receiptsplit.ledger import Ledger  # noqa: E402
from receiptsplit.models import Line  # noqa: E402

FX = ROOT / "fixtures"
POLICY = Policy.load(FX / "policy.json")


def load(rid):
    return Receipt.load(FX / "receipts" / f"{rid}.json"), Allocation.load(FX / "allocations" / f"{rid}.json")


def all_fixture_ids():
    return sorted(p.stem for p in (FX / "receipts").glob("*.json"))


def check_invariants(result):
    assert result["ok"], result["issues"]
    for r in result["receipts"]:
        assert sum(l["receipt_gross_cents"] for l in r["lines"]) == r["receipt_total_cents"]
        assert sum(l["card_cents"] for l in r["lines"]) == r["card_total_cents"]
    assert sum(t["card_cents"] for t in result["targets"].values()) == result["card_total_cents"]
    for t in result["targets"].values():
        assert sum(l["card_cents"] for l in t["lines"]) == t["card_cents"]


# ---------- distribute ----------

def test_distribute_exact_and_deterministic():
    rng = random.Random(3)
    for _ in range(2000):
        n = rng.randint(1, 8)
        w = {f"k{i}": rng.randint(0, 500) for i in range(n)}
        if sum(w.values()) == 0:
            w["k0"] = 1
        total = rng.randint(-5000, 5000)
        d = distribute(total, w)
        assert sum(d.values()) == total
        assert d == distribute(total, w)
        for k in w:  # never more than one cent away from the exact share
            assert abs(d[k] - total * w[k] / sum(w.values())) < 1


def test_distribute_ties_go_to_first_key():
    assert distribute(100, {"a": 1, "b": 1, "c": 1}) == {"a": 34, "b": 33, "c": 33}
    assert distribute(1, {"a": 1, "b": 1}) == {"a": 1, "b": 0}


# ---------- engine on fixtures ----------

def test_every_fixture_reconciles():
    for rid in all_fixture_ids():
        r, a = load(rid)
        check_invariants(allocate([r], [a], POLICY))


def test_rigi_tax_is_spread_proportionally():
    r, a = load("rigi-2026-09-20")
    res = allocate([r], [a], POLICY)
    lines = {l["id"]: l for l in res["receipts"][0]["lines"]}
    # 23.95 tax on 133.03 subtotal: every line grows by ~18 %, exactly to the cent in total
    assert r.extras_cents == 2395
    assert lines["l4"]["receipt_gross_cents"] == 6500  # 55.08 * 156.98/133.03 = 64.995 -> rounds within the remainder scheme
    assert sum(l["receipt_gross_cents"] for l in lines.values()) == 15698
    assert res["receipts"][0]["card_total_cents"] == 5337
    assert abs(res["receipts"][0]["implied_rate"] - 0.34) < 0.001


def test_handover_example_totals_and_notes():
    """The 6 Nov 2026 Apotekku + Pepito batch must reproduce the handover's figures and notes byte for byte."""
    recs, allocs = zip(load("example-usd-apotekku-2026-11-06"), load("example-usd-pepito-2026-11-06"))
    res = allocate(recs, allocs, POLICY)
    check_invariants(res)
    assert res["targets"]["daughter"]["card_cents"] == 855
    assert res["targets"]["daily"]["card_cents"] == 1949
    assert res["targets"]["unassigned"]["card_cents"] == 2079
    assert res["card_total_cents"] == 4883
    daughter = render_notes(res["targets"]["daughter"], "USD", POLICY)
    assert daughter == (
        "Apotekku — 06 Nov 2026\n"
        "$4.77 Youvit Multivitamin for Kids (30 days)\n"
        "\n"
        "Pepito Market — 06 Nov 2026\n"
        "$3.04 Merries diapers L\n"
        "$0.74 Paseo antibacterial wipes (25 sheets)\n"
        "----\n"
        "Total: $8.55"
    )
    daily = render_notes(res["targets"]["daily"], "USD", POLICY)
    assert daily == (
        "Apotekku — 06 Nov 2026\n"
        "$4.82 Altamed nitrile gloves L (100 pcs)\n"
        "\n"
        "Pepito Market — 06 Nov 2026\n"
        "$4.96 Earth Choice CLR Aqua 750 ml\n"
        "$4.96 Earth Choice Shower Clean 600 ml\n"
        "$4.75 Dr. Beckmann Washing Machine Cleaner 250 ml\n"
        "----\n"
        "Total: $19.49"
    )


def test_publish_requests_shares_and_fingerprints():
    recs, allocs = zip(load("example-usd-apotekku-2026-11-06"), load("example-usd-pepito-2026-11-06"))
    res = allocate(recs, allocs, POLICY)
    reqs = {r["target"]: r for r in build_publish_requests(res, POLICY, "2026-11-06")}
    assert reqs["daughter"]["owed_cents"] == {"me": 428, "supi": 427}
    assert reqs["daily"]["owed_cents"] == {"me": 975, "supi": 974}
    assert reqs["daughter"]["description"] == "Daughter 06 Nov 2026"
    assert reqs["unassigned"]["status"] == "blocked"
    for r in reqs.values():
        assert sum(r["owed_cents"].values()) in (r["cost_cents"], 0)
    # fingerprints are stable across runs and differ between targets
    again = {r["target"]: r["fingerprint"] for r in build_publish_requests(allocate(recs, allocs, POLICY), POLICY, "2026-11-06")}
    assert all(again[t] == reqs[t]["fingerprint"] for t in reqs)
    assert len({r["fingerprint"] for r in reqs.values()}) == len(reqs)


def test_ledger_refuses_duplicates(tmp_path=None):
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    recs, allocs = zip(load("example-usd-apotekku-2026-11-06"), load("example-usd-pepito-2026-11-06"))
    reqs = build_publish_requests(allocate(recs, allocs, POLICY), POLICY, "2026-11-06")
    led = Ledger(tmp / "ledger.json")
    first = led.record_draft(reqs[0])
    second = led.record_draft(reqs[0])
    assert first is second or first["recorded_at"] == second["recorded_at"]
    assert len(Ledger(tmp / "ledger.json").entries) == 1
    led.mark_published(reqs[0]["fingerprint"], "entered by hand")
    try:
        led.mark_published(reqs[0]["fingerprint"])
        assert False, "second publish must fail"
    except ValueError:
        pass


def test_real_pepito_receipt_idr_to_usd():
    """Real 6 Nov Pepito receipt (Drive OCR): 592,484 IDR paid, 33.44 USD charged."""
    r, a = load("pepito-2026-11-06")
    assert r.lines_sum == 59248400 and r.extras_cents == 0
    res = allocate([r], [a], POLICY)
    check_invariants(res)
    t = res["targets"]
    assert (t["daughter"]["card_cents"], t["daily"]["card_cents"], t["personal:me"]["card_cents"]) == (377, 1468, 1499)
    assert abs(res["receipts"][0]["implied_rate"] - 3344 / 59248400) < 1e-12
    notes = render_notes(t["daily"], "USD", POLICY)
    assert notes.endswith("----\nTotal: $14.68") and "$4.97 Earth Choice CLR Aqua 750 ml" in notes


def test_real_batch_6_nov_apotekku_and_pepito():
    """Both real 6 Nov receipts in one batch: one expense per target, Christian's own items stay out of Splitwise."""
    recs, allocs = zip(load("apotekku-2026-11-06"), load("pepito-2026-11-06"))
    res = allocate(recs, allocs, POLICY)
    check_invariants(res)
    assert res["ok"] and not [i for i in res["issues"] if i["level"] == "warning"]
    t = res["targets"]
    assert t["daughter"]["card_cents"] == 477 + 377 == 854
    assert t["daily"]["card_cents"] == 482 + 1468 == 1950
    assert t["personal:me"]["card_cents"] == 580 + 1499 == 2079
    assert res["card_total_cents"] == 1539 + 3344
    reqs = {r["target"]: r for r in build_publish_requests(res, POLICY, "2026-11-06")}
    assert reqs["daughter"]["owed_cents"] == {"me": 427, "supi": 427}
    assert reqs["daily"]["owed_cents"] == {"me": 975, "supi": 975}
    assert reqs["personal:me"]["owed_cents"] == {"me": 2079} and reqs["personal:me"]["status"] == "self"
    assert reqs["daughter"]["status"] == reqs["daily"]["status"] == "draft"
    assert render_notes(t["daughter"], "USD", POLICY).startswith("Apotekku — 06 Nov 2026\n$4.77 Youvit Multivitamin for Kids (30 days)\n\nPepito Market — 06 Nov 2026\n$3.04 ")


# ---------- edge cases ----------

def _receipt(lines, total, cur="IDR", **kw):
    return Receipt(id="x", merchant="M", date="2026-11-06", currency=cur,
                   lines=[Line(id=f"l{i}", name=f"item {i}", price_cents=c) for i, c in enumerate(lines)], total_cents=total, **kw)


def test_idr_receipt_converted_to_usd_card_charge():
    # 123,450 IDR printed, 7.89 USD actually charged (implied rate includes the bank's margin)
    r = _receipt([50000, 45000, 28450], 123450)
    a = Allocation(receipt_id="x", paid_by="me", targets={"l0": "daughter", "l1": "daily", "l2": "shared"}, card_currency="USD", card_amount_cents=789)
    res = allocate([r], [a], POLICY)
    check_invariants(res)
    t = res["targets"]
    assert t["daughter"]["card_cents"] + t["daily"]["card_cents"] + t["shared"]["card_cents"] == 789
    # 789 * 50000/123450 = 319.56, but the two larger remainders (.83 and .60) take the two leftover cents
    assert t["daughter"]["card_cents"] == 319 and t["daily"]["card_cents"] == 288 and t["shared"]["card_cents"] == 182


def test_negative_discount_line_and_receipt_level_discount():
    # 10.00 + 6.00 - 2.00 voucher line = 14.00, then receipt-level rounding to 13.90
    r = _receipt([1000, 600, -200], 1390, cur="EUR")
    a = Allocation(receipt_id="x", paid_by="me", targets={"l0": "shared", "l1": "shared", "l2": "shared"})
    res = allocate([r], [a], POLICY)
    check_invariants(res)
    gross = [l["receipt_gross_cents"] for l in res["receipts"][0]["lines"]]
    assert gross[2] == -200  # a discount line never absorbs extras
    assert gross[0] + gross[1] == 1590


def test_errors_are_reported_not_guessed():
    r = _receipt([1000], 1000, cur="EUR")
    a = Allocation(receipt_id="x", paid_by="nobody", targets={"l0": "weird", "l9": "shared"})
    res = allocate([r], [a], POLICY)
    assert not res["ok"]
    msgs = " | ".join(i["message"] for i in res["issues"])
    assert "unknown payer" in msgs and "no share rule" in msgs and "unknown line" in msgs
    try:
        build_publish_requests(res, POLICY, "2026-11-06")
        assert False
    except ValueError:
        pass


def test_mixed_card_currencies_in_one_batch_is_an_error():
    r1, r2 = _receipt([100], 100), _receipt([100], 100)
    r2.id = "y"
    a1 = Allocation("x", "me", {"l0": "shared"}, "USD", 7)
    a2 = Allocation("y", "me", {"l0": "shared"}, "EUR", 6)
    res = allocate([r1, r2], [a1, a2], POLICY)
    assert not res["ok"] and any("differs from the batch" in i["message"] for i in res["issues"])


def test_low_confidence_and_subtotal_mismatch_are_warnings():
    r = _receipt([1000, 500], 1600, cur="EUR", subtotal_cents=1400, tax_cents=200, service_cents=0, discount_cents=0)
    r.lines[0].confidence = 0.3
    a = Allocation("x", "me", {"l0": "shared", "l1": "shared"})
    res = allocate([r], [a], POLICY)
    assert res["ok"]
    levels = [i["level"] for i in res["issues"]]
    assert "warning" in levels and "error" not in levels
    assert any("confidence" in i["message"] for i in res["issues"])
    assert any("printed subtotal" in i["message"] for i in res["issues"])


def test_random_batches_always_reconcile():
    rng = random.Random(11)
    targets = ["daughter", "daily", "shared", "personal:me", "personal:supi", "unassigned"]
    for _ in range(300):
        recs, allocs = [], []
        for j in range(rng.randint(1, 4)):
            n = rng.randint(1, 9)
            lines = [rng.randint(-300, 50000) for _ in range(n)]
            if all(c <= 0 for c in lines):
                lines[0] = 1000
            total = max(1, sum(lines) + rng.randint(-500, 5000))
            r = _receipt(lines, total)
            r.id = f"r{j}"
            recs.append(r)
            allocs.append(Allocation(f"r{j}", "me", {f"l{i}": rng.choice(targets) for i in range(n)}, "USD", rng.randint(1, 10000)))
        check_invariants(allocate(recs, allocs, POLICY))


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print("FAIL", name, "->", repr(e))
    sys.exit(1 if fails else 0)
