"""Search budget and sequence-dependency tests."""

from __future__ import annotations

import unittest

from atm_optimizer.planner import optimize
from atm_optimizer.validate import parse_input


class BudgetTest(unittest.TestCase):
    def _raw(self, budget):
        raw = {
            "cassette_count": 3,
            "denominations": [10, 20, 50],
            "cassette_capacity": 6,
            "total_note_limit": 12,
            "initial_cash_limit": 800,
            "withdrawals": [60, 40, 50, 30],
            "penalties": [100, 100, 100, 100],
        }
        if budget is not None:
            raw["search_budget"] = budget
        return raw

    def test_unlimited_budget_is_optimal(self) -> None:
        result = optimize(parse_input(self._raw(None)))
        self.assertEqual(result.status, "optimal")
        self.assertTrue(result.optimal)
        self.assertEqual(result.upper_bound, result.lower_bound)

    def test_tiny_budget_marks_incomplete(self) -> None:
        result = optimize(parse_input(self._raw(1)))
        self.assertEqual(result.status, "incomplete")
        self.assertFalse(result.optimal)
        self.assertLessEqual(result.explored_states, 1)
        self.assertEqual(result.explored_states, 1)
        self.assertIsNone(result.plan)
        self.assertEqual(result.upper_bound[0], 10**18)

    def test_partial_budget_has_bounds_and_incumbent(self) -> None:
        full = optimize(parse_input(self._raw(None)))
        result = optimize(parse_input(self._raw(300)))
        self.assertFalse(result.optimal)
        self.assertEqual(result.status, "incomplete")
        self.assertLessEqual(result.explored_states, 500)
        if result.plan is not None:
            upper = result.upper_bound
            self.assertEqual(len(upper), 4)
            self.assertEqual(upper[0], result.plan.objectives.penalty_total)
            # incumbent cannot beat the proven optimum lexicographically
            opt_vec = (
                full.plan.objectives.penalty_total,
                full.plan.objectives.transport_reload_cost,
                full.plan.objectives.initial_cash_used,
                full.plan.objectives.dispensed_notes,
            )
            self.assertGreaterEqual(upper, opt_vec)
        for low, high in zip(result.lower_bound, result.upper_bound):
            self.assertLessEqual(low, high)

    def test_budget_just_above_required_reaches_optimal(self) -> None:
        full = optimize(parse_input(self._raw(None)))
        result = optimize(parse_input(self._raw(full.explored_states)))
        self.assertTrue(result.optimal)
        self.assertEqual(result.upper_bound, full.upper_bound)

    def test_forced_failure_reflected_in_lower_bound(self) -> None:
        # 25 cannot be paid with 10/20 notes at all.
        raw = {
            "cassette_count": 2,
            "denominations": [10, 20],
            "cassette_capacity": 5,
            "total_note_limit": 10,
            "initial_cash_limit": 500,
            "withdrawals": [25],
            "penalties": [77],
            "search_budget": 1,
        }
        result = optimize(parse_input(raw))
        self.assertFalse(result.optimal)
        self.assertGreaterEqual(result.lower_bound[0], 77)


class SequenceDependencyTest(unittest.TestCase):
    def test_greedy_choice_blocks_later_request(self) -> None:
        # Stock (10:1, 20:2). Requests [30, 20]. Paying 30 as (1,1) leaves
        # (0,1) so 20 still works; a planner that used (3,0) would need three
        # 10 notes, but the only loading with one 10 forces the coupled plan.
        raw = {
            "cassette_count": 2,
            "denominations": [10, 20],
            "cassette_capacity": 2,
            "total_note_limit": 4,
            "initial_cash_limit": 500,
            "withdrawals": [30, 20],
            "penalties": [100, 100],
        }
        result = optimize(parse_input(raw))
        plan = result.plan
        self.assertEqual(plan.objectives.penalty_total, 0)
        self.assertEqual(plan.denomination_vector, (10, 20))
        self.assertEqual(plan.initial_counts_vector, (1, 2))
        actions = [o.dispensed for o in plan.outcomes]
        self.assertEqual(actions, [(1, 1), (0, 1)])

    def test_consuming_high_denomination_now_is_wrong_for_later(self) -> None:
        # (20:2, 50:1); requests [50, 40]. Satisfying first with the 50 note
        # then 2x20 is feasible and canonical; a greedy 20+... cannot make 50.
        raw = {
            "cassette_count": 2,
            "denominations": [20, 50],
            "cassette_capacity": 2,
            "total_note_limit": 4,
            "initial_cash_limit": 500,
            "withdrawals": [50, 40],
            "penalties": [100, 100],
        }
        result = optimize(parse_input(raw))
        plan = result.plan
        self.assertEqual(plan.objectives.penalty_total, 0)
        actions = [o.dispensed for o in plan.outcomes]
        self.assertEqual(actions, [(0, 1), (2, 0)])


if __name__ == "__main__":
    unittest.main()
