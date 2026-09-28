"""Randomized cross-check of the optimized solver against brute force."""

from __future__ import annotations

import random
import unittest

from tests.test_oracle import CASES, _plan_signature, brute_force_optimum
from atm_optimizer.planner import optimize
from atm_optimizer.validate import parse_input


class FuzzTest(unittest.TestCase):
    def test_random_small_instances_match_oracle(self) -> None:
        rng = random.Random(20260928)
        for trial in range(60):
            k = rng.randint(2, 3)
            denoms = rng.choice(
                [(10, 20), (10, 20, 50), (5, 20), (10, 50)]
            )
            capacity = rng.randint(1, 3)
            note_limit = rng.randint(k, k * capacity)
            m = rng.randint(0, 3)
            amounts = [rng.choice([0, 10, 20, 25, 30, 40, 50, 60]) for _ in range(m)]
            penalties = [rng.choice([0, 1, 7, 100]) for _ in range(m)]
            raw = {
                "cassette_count": k,
                "denominations": list(denoms),
                "cassette_capacity": capacity,
                "total_note_limit": note_limit,
                "initial_cash_limit": rng.choice([0, 50, 200, 1000]),
                "withdrawals": amounts,
                "penalties": penalties,
                "transport_cost_per_note": rng.choice([0, 1, 2]),
                "load_cost_per_cassette": rng.choice([0, 3, 5]),
            }
            inp = parse_input(raw)
            (_, _), oracle_key = brute_force_optimum(inp)
            result = optimize(inp)
            with self.subTest(trial=trial, raw=raw):
                self.assertTrue(result.optimal)
                self.assertEqual(_plan_signature(result), oracle_key)


if __name__ == "__main__":
    unittest.main()
