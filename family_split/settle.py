"""
Debt settlement with the minimum number of transfers.

Given net balances per person (positive = is owed money, negative = owes),
find the fewest bank transfers that make everybody even. This is the exact
optimisation problem the Familienkasse app solves in the browser; here it is
in Python, in two flavours that tie into the course:

1. `settle_dp` (section 3 flavour, tree search / dynamic programming):
   min transfers = n - (max number of disjoint groups whose balances sum to 0).
   Solved exactly with a DP over subsets, fine up to ~20 people.
2. `settle_ilp` (section 4 flavour, integer programming with PuLP):
   binary "is there a transfer i -> j" variables plus flow conservation.
   Optional, only runs when PuLP is installed (`pip install pulp`).

All money is handled in integer cents so the sums are exact.

Run `python settle.py` to see both on the Rigi receipt from 20 Sep 2026.
"""

from __future__ import annotations

from itertools import combinations
from typing import Dict, List, Tuple

Transfer = Tuple[str, str, int]  # (from, to, cents)


def _greedy_group(balances: Dict[str, int]) -> List[Transfer]:
    """Settle one zero-sum group by repeatedly matching the largest creditor
    with the largest debtor. A group of k people needs at most k-1 transfers."""
    b = dict(balances)
    out: List[Transfer] = []
    while True:
        creditors = sorted((p for p in b if b[p] > 0), key=lambda p: -b[p])
        debtors = sorted((p for p in b if b[p] < 0), key=lambda p: b[p])
        if not creditors or not debtors:
            return out
        c, d = creditors[0], debtors[0]
        amt = min(b[c], -b[d])
        out.append((d, c, amt))
        b[c] -= amt
        b[d] += amt


def settle_greedy(balances: Dict[str, int]) -> List[Transfer]:
    """Plain greedy over everybody. Fast, usually good, not always optimal."""
    return _greedy_group({p: v for p, v in balances.items() if v})


def settle_dp(balances: Dict[str, int]) -> List[Transfer]:
    """Exact minimum-transfer settlement via DP over subsets."""
    people = [p for p, v in balances.items() if v]
    n = len(people)
    if n == 0:
        return []
    if sum(balances[p] for p in people) != 0:
        raise ValueError("balances must sum to zero")
    size = 1 << n
    subset_sum = [0] * size
    for m in range(1, size):
        low = m & -m
        i = low.bit_length() - 1
        subset_sum[m] = subset_sum[m ^ low] + balances[people[i]]
    best = [0] * size
    parent = [0] * size
    for m in range(1, size):
        b, bp = -1, 0
        for i in range(n):
            if m >> i & 1:
                prev = m ^ (1 << i)
                if best[prev] > b:
                    b, bp = best[prev], prev
        best[m] = b + (1 if subset_sum[m] == 0 else 0)
        parent[m] = bp
    # Walk back from the full set; every zero-sum mask closes a group.
    groups: List[List[str]] = []
    cur, group = size - 1, []
    while cur:
        prev = parent[cur]
        group.append(people[(cur ^ prev).bit_length() - 1])
        if subset_sum[prev] == 0:
            groups.append(group)
            group = []
        cur = prev
    if group:
        groups.append(group)
    transfers: List[Transfer] = []
    for g in groups:
        transfers += _greedy_group({p: balances[p] for p in g})
    return transfers


def settle_ilp(balances: Dict[str, int]) -> List[Transfer]:
    """Exact settlement as a mixed-integer program (needs PuLP).

    Variables:  x[i][j] >= 0   cents moved from i to j
                y[i][j] in {0,1}  whether that transfer exists
    Constraints: outflow - inflow == balance_i for everyone (owe-ers pay,
                 owed-ers receive), x[i][j] <= M * y[i][j].
    Objective:   minimise sum of y.
    """
    import pulp  # noqa: F401  (import here so the module works without it)

    people = [p for p, v in balances.items() if v]
    if not people:
        return []
    big_m = sum(abs(v) for v in balances.values())
    prob = pulp.LpProblem("min_transfers", pulp.LpMinimize)
    pairs = [(i, j) for i in people for j in people if i != j]
    x = {(i, j): pulp.LpVariable(f"x_{i}_{j}", lowBound=0) for i, j in pairs}
    y = {(i, j): pulp.LpVariable(f"y_{i}_{j}", cat="Binary") for i, j in pairs}
    prob += pulp.lpSum(y.values())
    for i, j in pairs:
        prob += x[i, j] <= big_m * y[i, j]
    for p in people:
        outflow = pulp.lpSum(x[p, j] for j in people if j != p)
        inflow = pulp.lpSum(x[i, p] for i in people if i != p)
        # a debtor (negative balance) must send out what they owe
        prob += outflow - inflow == -balances[p]
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    return [(i, j, int(round(x[i, j].value()))) for i, j in pairs if y[i, j].value() and y[i, j].value() > 0.5]


def check(balances: Dict[str, int], transfers: List[Transfer]) -> bool:
    """True when the transfers settle the balances exactly."""
    b = dict(balances)
    for src, dst, amt in transfers:
        b[src] += amt
        b[dst] -= amt
    return all(v == 0 for v in b.values())


def min_transfers_bruteforce(balances: Dict[str, int]) -> int:
    """Reference answer for tests: n minus the max number of disjoint zero-sum groups."""
    people = [p for p, v in balances.items() if v]
    n = len(people)
    best = 0
    zero_sets = [frozenset(c) for r in range(1, n + 1) for c in combinations(people, r) if sum(balances[p] for p in c) == 0]

    def rec(remaining: frozenset, count: int) -> None:
        nonlocal best
        best = max(best, count)
        if not remaining:
            return
        first = min(remaining)
        for z in zero_sets:
            if first in z and z <= remaining:
                rec(remaining - z, count + 1)

    rec(frozenset(people), 0)
    return n - best


def split_items(total: int, items: List[Tuple[str, int, List[str]]], everyone: List[str]) -> Dict[str, int]:
    """Itemised split like the app: each item is shared equally by the people
    listed for it (or everyone when the list is empty); the remainder up to
    `total` (tax, tip, rounding) is spread proportionally to each person's
    item subtotal. Largest-remainder rounding keeps the cents exact."""

    def distribute(amount: int, weights: Dict[str, float]) -> Dict[str, int]:
        ids = [k for k, w in weights.items() if w > 0]
        wsum = sum(weights[k] for k in ids)
        if not ids or wsum <= 0:
            return {}
        raw = {k: amount * weights[k] / wsum for k in ids}
        out = {k: int(raw[k] // 1) for k in ids}
        left = amount - sum(out.values())
        for k in sorted(ids, key=lambda k: raw[k] - out[k], reverse=True)[:left]:
            out[k] += 1
        return out

    per: Dict[str, int] = {}
    items_sum = 0
    for _name, price, people in items:
        items_sum += price
        share = distribute(price, {p: 1 for p in (people or everyone)})
        for p, c in share.items():
            per[p] = per.get(p, 0) + c
    extra = total - items_sum
    if extra:
        weights = {p: float(c) for p, c in per.items()} if per else {p: 1.0 for p in everyone}
        for p, c in distribute(abs(extra), weights).items():
            per[p] = per.get(p, 0) + (c if extra > 0 else -c)
    return per


if __name__ == "__main__":
    # The Rigi Gastrodouqan receipt, 20 Sep 2026, in GEL cents.
    everyone = ["A", "B", "C"]
    receipt = [
        ("2 Mineral Water Borjomi", 932, []),        # shared by all
        ("Khoncha", 3220, []),                       # shared platter
        ("Mushroom Soup", 1864, ["A"]),
        ("Beef Stew in Phyllo Dough", 5508, ["B"]),
        ("Lomtagora shoti bread", 254, []),
        ("Matsoni Ice Cream", 1525, ["C"]),
    ]
    total = 15698  # subtotal 133.03 + tax 23.95
    shares = split_items(total, receipt, everyone)
    print("Rigi receipt, per person incl. proportional tax (GEL):")
    for p in everyone:
        print(f"  {p}: {shares[p] / 100:8.2f}")
    print(f"  sum {sum(shares.values()) / 100:8.2f}  (receipt {total / 100:.2f})\n")

    # Suppose A paid the whole bill, B and C owe A their shares.
    balances = {p: -shares[p] for p in everyone}
    balances["A"] += total
    print("Balances (positive = is owed):", balances)
    print("DP settlement:", settle_dp(balances))

    # A case where greedy is NOT optimal: {Ben, Anna, Cem} and {Dana, Eli, Finn} cancel separately.
    tricky = {"Anna": -800, "Ben": 600, "Cem": -200, "Dana": 300, "Eli": 400, "Finn": -300}
    g = settle_greedy(tricky)
    d = settle_dp(tricky)
    print(f"\nGreedy needs {len(g)} transfers, DP needs {len(d)}:", d)
    assert check(tricky, d) and len(d) == min_transfers_bruteforce(tricky)
    try:
        i = settle_ilp(tricky)
        print(f"ILP (PuLP) needs {len(i)} transfers:", i)
        assert check(tricky, i) and len(i) == len(d)
    except ImportError:
        print("PuLP not installed, skipping the ILP variant (pip install pulp).")
