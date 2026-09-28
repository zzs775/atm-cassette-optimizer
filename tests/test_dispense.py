"""Finite-stock exact dispense enumeration tests."""

from __future__ import annotations

import itertools
import unittest

from atm_optimizer.dispense import can_pay, enumerate_dispenses


class DispenseTest(unittest.TestCase):
    def _brute(self, amount, den, stock):
        return sorted(
            tuple(c)
            for c in itertools.product(*(range(s + 1) for s in stock))
            if sum(a * b for a, b in zip(c, den)) == amount
        )

    def test_zero_amount_single_zero_vector(self) -> None:
        self.assertEqual(enumerate_dispenses(0, (10, 20), (3, 3)), [(0, 0)])

    def test_limited_stock_excludes_unbounded_options(self) -> None:
        # 40 = 2x20 only when only one 10 note is available (4x10 excluded).
        self.assertEqual(enumerate_dispenses(40, (10, 20), (1, 3)), [(0, 2)])

    def test_repeated_denomination_cassettes(self) -> None:
        got = enumerate_dispenses(20, (10, 10), (2, 2))
        self.assertEqual(got, [(0, 2), (1, 1), (2, 0)])

    def test_impossible_amount(self) -> None:
        self.assertEqual(enumerate_dispenses(25, (10, 20), (5, 5)), [])
        self.assertFalse(can_pay(25, (10, 20), (5, 5)))

    def test_output_is_sorted(self) -> None:
        got = enumerate_dispenses(60, (10, 20, 50), (3, 2, 2))
        self.assertEqual(got, sorted(got))

    def test_matches_brute_force_on_cases(self) -> None:
        cases = [
            (30, (10, 20), (3, 3)),
            (60, (10, 20, 50), (3, 2, 2)),
            (50, (5, 10, 25), (4, 4, 1)),
            (100, (10, 20, 50), (2, 2, 2)),
            (0, (10, 20), (0, 0)),
            (30, (10, 10), (3, 3)),
        ]
        for amount, den, stock in cases:
            with self.subTest(amount=amount, den=den, stock=stock):
                self.assertEqual(
                    enumerate_dispenses(amount, den, stock),
                    self._brute(amount, den, stock),
                )

    def test_unused_zero_face_cassette(self) -> None:
        self.assertEqual(enumerate_dispenses(20, (0, 20), (0, 1)), [(0, 1)])


if __name__ == "__main__":
    unittest.main()
