"""Property tests for settle.py. Run with `python -m pytest family_split` or `python family_split/test_settle.py`."""

import random

from settle import check, min_transfers_bruteforce, settle_dp, settle_greedy, split_items


def random_balances(rng, n):
    vals = [rng.randint(-2000, 2000) for _ in range(n - 1)]
    vals.append(-sum(vals))
    return {f"p{i}": v for i, v in enumerate(vals)}


def test_dp_is_optimal_and_valid():
    rng = random.Random(7)
    for _ in range(300):
        n = rng.randint(1, 7)
        bal = random_balances(rng, n)
        t = settle_dp(bal)
        assert check(bal, t)
        assert len(t) == min_transfers_bruteforce(bal)
        assert len(t) <= len(settle_greedy(bal))


def test_greedy_can_be_beaten():
    tricky = {"Anna": -800, "Ben": 600, "Cem": -200, "Dana": 300, "Eli": 400, "Finn": -300}
    assert len(settle_greedy(tricky)) > len(settle_dp(tricky))


def test_item_split_sums_exactly():
    everyone = ["A", "B", "C"]
    items = [("water", 932, []), ("soup", 1864, ["A"]), ("stew", 5508, ["B"]), ("bread", 254, []), ("ice", 1525, ["C"]), ("platter", 3220, [])]
    shares = split_items(15698, items, everyone)
    assert sum(shares.values()) == 15698
    assert shares["B"] > shares["A"] > shares["C"]


if __name__ == "__main__":
    test_dp_is_optimal_and_valid()
    test_greedy_can_be_beaten()
    test_item_split_sums_exactly()
    print("all tests passed")
