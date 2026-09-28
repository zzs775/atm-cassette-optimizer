"""Determinism and canonical tie-break tests.

Covers: repeated-denomination cassettes, input denomination-order changes,
different insertion orders, canonical JSON byte equality, and explicit tie
situations resolved by (faces, counts, dispense prefix).
"""

from __future__ import annotations

import json
import unittest

from atm_optimizer.planner import optimize
from atm_optimizer.protocol import dumps_canonical, result_to_jsonable
from atm_optimizer.validate import parse_input


def solve(raw):
    inp = parse_input(raw)
    return inp, optimize(inp)


def canonical_bytes(raw):
    inp, result = solve(raw)
    return dumps_canonical(result_to_jsonable(inp, result))


class DeterminismTest(unittest.TestCase):
    def test_denomination_input_order_invariant(self) -> None:
        raw_a = {
            "cassette_count": 3,
            "denominations": [10, 20, 50],
            "cassette_capacity": 4,
            "total_note_limit": 8,
            "initial_cash_limit": 500,
            "withdrawals": [60, 70, 40],
            "penalties": [10, 10, 10],
        }
        raw_b = dict(raw_a, denominations=[50, 10, 20])
        raw_c = dict(raw_a, denominations=[20, 50, 10, 10])
        out_a = canonical_bytes(raw_a)
        self.assertEqual(out_a, canonical_bytes(raw_b))
        self.assertEqual(out_a, canonical_bytes(raw_c))

    def test_repeated_runs_identical(self) -> None:
        raw = {
            "cassette_count": 2,
            "denominations": [10, 20],
            "cassette_capacity": 3,
            "total_note_limit": 6,
            "initial_cash_limit": 500,
            "withdrawals": [30, 30],
            "penalties": [5, 5],
        }
        self.assertEqual(canonical_bytes(raw), canonical_bytes(json.loads(json.dumps(raw))))

    def test_canonical_tie_face_vector_prefers_smaller(self) -> None:
        # 40 then 20, big penalties: two 20-note cassettes versus 10/20 mix.
        # Cheapest equal objectives tie is resolved by face vector.
        raw = {
            "cassette_count": 2,
            "denominations": [10, 20],
            "cassette_capacity": 3,
            "total_note_limit": 6,
            "initial_cash_limit": 500,
            "withdrawals": [20, 20, 20],
            "penalties": [1, 1, 1],
        }
        inp, result = solve(raw)
        plan = result.plan
        self.assertEqual(plan.denomination_vector, (0, 20))
        self.assertEqual(plan.initial_counts_vector, (0, 3))

    def test_unused_cassette_wins_face_vector_tie(self) -> None:
        # A single 20 note suffices; the canonical face vector keeps cassette 0
        # unused: (0, 20) with counts (0, 1), not (20, 20) with (1, 0).
        raw = {
            "cassette_count": 2,
            "denominations": [20],
            "cassette_capacity": 3,
            "total_note_limit": 6,
            "initial_cash_limit": 500,
            "withdrawals": [20],
            "penalties": [1],
        }
        inp, result = solve(raw)
        plan = result.plan
        self.assertEqual(plan.denomination_vector, (0, 20))
        self.assertEqual(plan.initial_counts_vector, (0, 1))
        self.assertEqual(plan.outcomes[0].dispensed, (0, 1))

    def test_dispense_prefix_tie_break_is_le_numeric_vector(self) -> None:
        # Loading (20,20)/(2,0): after first (1,0) only cassette 0 is empty,
        # so the second withdrawal must come from cassette 1. The prefix that
        # reaches this with lexicographically smaller vectors wins.
        raw = {
            "cassette_count": 2,
            "denominations": [20],
            "cassette_capacity": 2,
            "total_note_limit": 4,
            "initial_cash_limit": 500,
            "withdrawals": [20, 20],
            "penalties": [1, 1],
        }
        inp, result = solve(raw)
        # Canonical: one cassette suffices with (0,20)/(0,2) and (0,1),(0,1).
        actions = [o.dispensed for o in result.plan.outcomes]
        self.assertEqual(actions, [(0, 1), (0, 1)])
        self.assertEqual(result.plan.denomination_vector, (0, 20))
        self.assertEqual(result.plan.initial_counts_vector, (0, 2))

    def test_json_sorted_keys_and_trailing_newline(self) -> None:
        raw = {
            "cassette_count": 2,
            "denominations": [10, 20],
            "cassette_capacity": 2,
            "total_note_limit": 4,
            "initial_cash_limit": 500,
            "withdrawals": [20],
            "penalties": [1],
        }
        text = canonical_bytes(raw)
        self.assertTrue(text.endswith("\n"))
        decoded = json.loads(text)
        re_encoded = json.dumps(decoded, sort_keys=True, indent=2,
                                separators=(",", ": ")) + "\n"
        self.assertEqual(text, re_encoded)


if __name__ == "__main__":
    unittest.main()
