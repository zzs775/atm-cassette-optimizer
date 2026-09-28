"""Exact change generation under finite per-cassette stock.

Given the (possibly repeated) denomination of each cassette and the number of
notes currently in each cassette, enumerate every way to pay an exact amount.
This is a complete enumeration: the sequence optimizer needs every candidate
dispense action, not just the locally note-minimal one.
"""

from __future__ import annotations

from math import gcd


def enumerate_dispenses(
    amount: int,
    denominations: tuple[int, ...],
    stock: tuple[int, ...],
) -> list[tuple[int, ...]]:
    """Enumerate every note-count vector that exactly pays amount.

    Results are returned in lexicographically ascending order of the count
    vector (cassette 0 is the slowest-varying coordinate). A zero-amount
    withdrawal yields the single all-zero vector.
    """
    k = len(denominations)
    if len(stock) != k:
        raise ValueError("denominations and stock must have equal length")
    if amount < 0:
        raise ValueError("amount must be non-negative")
    if amount == 0:
        return [tuple([0] * k)]

    suffix_max = [0] * (k + 1)
    for i in range(k - 1, -1, -1):
        suffix_max[i] = suffix_max[i + 1] + denominations[i] * stock[i]

    suffix_gcd = [0] * (k + 1)
    for i in range(k - 1, -1, -1):
        suffix_gcd[i] = gcd(denominations[i], suffix_gcd[i + 1])

    results: list[tuple[int, ...]] = []
    chosen = [0] * k

    def dfs(i: int, remaining: int) -> None:
        if i == k - 1:
            face = denominations[i]
            if face == 0:
                if stock[i] == 0 and remaining == 0:
                    results.append(tuple(chosen))
            elif remaining % face == 0:
                count = remaining // face
                if 0 <= count <= stock[i]:
                    chosen[i] = count
                    results.append(tuple(chosen))
                    chosen[i] = 0
            return
        face = denominations[i]
        if face == 0:
            if stock[i] != 0:
                raise ValueError("zero-face cassette must be empty")
            chosen[i] = 0
            dfs(i + 1, remaining)
            return
        upper = min(stock[i], remaining // face)
        g = suffix_gcd[i + 1]
        for count in range(upper + 1):
            rest = remaining - count * face
            if rest == 0:
                chosen[i] = count
                results.append(tuple(chosen))
                chosen[i] = 0
                continue
            if suffix_max[i + 1] < rest:
                continue
            if g != 0 and rest % g != 0:
                continue
            chosen[i] = count
            dfs(i + 1, rest)
        chosen[i] = 0

    if suffix_max[0] >= amount:
        g0 = suffix_gcd[0]
        if g0 == 0 or amount % g0 == 0:
            dfs(0, amount)
    return results


def can_pay(
    amount: int,
    denominations: tuple[int, ...],
    stock: tuple[int, ...],
) -> bool:
    """Return True iff at least one exact dispense vector exists."""
    if amount == 0:
        return True
    return bool(enumerate_dispenses(amount, denominations, stock))
