"""Full nested-optimization oracle tests.

A brute-force oracle enumerates every feasible loading and, per loading,
every feasible dispense/failure action sequence (no dominance pruning and no
primary cutoff), then selects the canonical minimum under
(penalty, cost, cash, notes, faces, counts, dispense-prefix). The optimized
planner must match it exactly on a battery of small scenarios including
finite stock, repeated denominations, sequence coupling and forced failures.
"""

from __future__ import annotations

import itertools
import unittest

from atm_optimizer import planner as planner_mod
from atm_optimizer import sequence as sequence_mod
from atm_optimizer.dispense import enumerate_dispenses
from atm_optimizer.loading import enumerate_loadings
from atm_optimizer.planner import optimize
from atm_optimizer.validate import parse_input


def _loading_cost(inp, loading):
    return (
        loading.notes * inp.transport_cost_per_note
        + loading.used_cassettes * inp.load_cost_per_cassette
    )


def _prefix_key(prefix):
    return tuple((0, ()) if action is None else (1, action) for action in prefix)


def brute_force_optimum(inp):
    best_key = None
    best = None
    for loading in enumerate_loadings(inp):
        states = [(loading.counts, ())]
        for t, amount in enumerate(inp.withdrawals):
            nxt = []
            for stock, prefix in states:
                for vec in enumerate_dispenses(amount, loading.faces, stock):
                    nxt.append((
                        tuple(s - d for s, d in zip(stock, vec)),
                        prefix + (vec,),
                    ))
                nxt.append((stock, prefix + (None,)))
            states = nxt
        for stock, prefix in states:
            penalty = sum(
                inp.penalties[t] for t, a in enumerate(prefix) if a is None
            )
            notes = sum(sum(a) for a in prefix if a is not None)
            key = (
                penalty,
                _loading_cost(inp, loading),
                loading.cash,
                notes,
                loading.faces,
                loading.counts,
                _prefix_key(prefix),
            )
            if best_key is None or key < best_key:
                best_key = key
                best = (loading, prefix)
    return best, best_key


def _plan_signature(result):
    plan = result.plan
    prefix = tuple(
        None if not o.satisfied else o.dispensed for o in plan.outcomes
    )
    return (
        plan.objectives.penalty_total,
        plan.objectives.transport_reload_cost,
        plan.objectives.initial_cash_used,
        plan.objectives.dispensed_notes,
        plan.denomination_vector,
        plan.initial_counts_vector,
        _prefix_key(prefix),
    )


CASES = [
    {
        "cassette_count": 2,
        "denominations": [10, 20],
        "cassette_capacity": 3,
        "total_note_limit": 6,
        "initial_cash_limit": 1000,
        "withdrawals": [30, 30],
        "penalties": [100, 100],
    },
    {
        "cassette_count": 2,
        "denominations": [10, 20],
        "cassette_capacity": 3,
        "total_note_limit": 6,
        "initial_cash_limit": 1000,
        "withdrawals": [20, 20, 20],
        "penalties": [100, 100, 100],
    },
    {
        "cassette_count": 2,
        "denominations": [10, 20],
        "cassette_capacity": 4,
        "total_note_limit": 6,
        "initial_cash_limit": 1000,
        "withdrawals": [40, 20, 30],
        "penalties": [50, 100, 5],
    },
    {
        "cassette_count": 3,
        "denominations": [10, 20, 50],
        "cassette_capacity": 3,
        "total_note_limit": 6,
        "initial_cash_limit": 400,
        "withdrawals": [60, 50, 20],
        "penalties": [7, 7, 7],
    },
    {
        "cassette_count": 2,
        "denominations": [20, 50],
        "cassette_capacity": 3,
        "total_note_limit": 4,
        "initial_cash_limit": 300,
        "withdrawals": [30, 40],
        "penalties": [100, 1],
    },
    {
        "cassette_count": 3,
        "denominations": [10, 50],
        "cassette_capacity": 3,
        "total_note_limit": 5,
        "initial_cash_limit": 300,
        "withdrawals": [60, 20, 50],
        "penalties": [3, 100, 3],
    },
    {
        "cassette_count": 2,
        "denominations": [10, 20],
        "cassette_capacity": 2,
        "total_note_limit": 4,
        "initial_cash_limit": 1000,
        "withdrawals": [0, 20],
        "penalties": [9, 9],
    },
    {
        "cassette_count": 2,
        "denominations": [10, 20],
        "cassette_capacity": 3,
        "total_note_limit": 6,
        "initial_cash_limit": 1000,
        "withdrawals": [25, 25],
        "penalties": [100, 100],
        "transport_cost_per_note": 2,
        "load_cost_per_cassette": 7,
    },
]


class OracleTest(unittest.TestCase):
    def assert_matches_oracle(self, raw) -> None:
        inp = parse_input(raw)
        (loading, prefix), oracle_key = brute_force_optimum(inp)
        old_bb = planner_mod.BRANCH_AND_BOUND
        planner_mod.BRANCH_AND_BOUND = True
        try:
            result = optimize(inp)
        finally:
            planner_mod.BRANCH_AND_BOUND = old_bb
        self.assertTrue(result.optimal)
        self.assertEqual(_plan_signature(result), oracle_key)

    def test_all_cases_match_brute_force(self) -> None:
        for i, raw in enumerate(CASES):
            with self.subTest(case=i):
                self.assert_matches_oracle(raw)

    def test_branch_and_bound_matches_unpruned(self) -> None:
        for i, raw in enumerate(CASES):
            inp = parse_input(raw)
            old_bb = planner_mod.BRANCH_AND_BOUND
            planner_mod.BRANCH_AND_BOUND = False
            try:
                full = optimize(inp)
            finally:
                planner_mod.BRANCH_AND_BOUND = old_bb
            pruned = optimize(parse_input(raw))
            with self.subTest(case=i):
                self.assertEqual(_plan_signature(pruned), _plan_signature(full))

    def test_dominance_pruning_matches_full_frontier(self) -> None:
        for i, raw in enumerate(CASES):
            inp = parse_input(raw)
            old_dom = sequence_mod.DOMINANCE_PRUNING
            sequence_mod.DOMINANCE_PRUNING = False
            planner_mod.BRANCH_AND_BOUND = False
            try:
                full = optimize(inp)
            finally:
                sequence_mod.DOMINANCE_PRUNING = old_dom
                planner_mod.BRANCH_AND_BOUND = True
            with self.subTest(case=i):
                self.assertEqual(
                    _plan_signature(full), _plan_signature(optimize(parse_input(raw)))
                )


if __name__ == "__main__":
    unittest.main()
