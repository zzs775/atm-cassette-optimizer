"""Protocol, replay-consistency and CLI integration tests."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest

from atm_optimizer.planner import optimize
from atm_optimizer.protocol import dumps_canonical, result_to_jsonable
from atm_optimizer.validate import parse_input


RAW = {
    "cassette_count": 3,
    "denominations": [50, 20, 10],
    "cassette_capacity": 6,
    "total_note_limit": 12,
    "initial_cash_limit": 800,
    "withdrawals": [60, 40, 50, 30],
    "penalties": [100, 100, 100, 100],
    "transport_cost_per_note": 2,
    "load_cost_per_cassette": 5,
}


class ProtocolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.inp = parse_input(RAW)
        self.result = optimize(self.inp)
        self.payload = result_to_jsonable(self.inp, self.result)

    def test_replay_recomputes_stock(self) -> None:
        plan = self.payload["plan"]
        stock = list(plan["initial_counts_vector"])
        for w in plan["withdrawals"]:
            self.assertEqual(w["stock_before"], stock)
            if w["satisfied"]:
                value = sum(
                    d * f
                    for d, f in zip(
                        w["dispensed"], w["denomination_vector"]
                    )
                )
                self.assertEqual(value, w["amount"])
                stock = [s - d for s, d in zip(stock, w["dispensed"])]
                self.assertTrue(all(s >= 0 for s in stock))
            else:
                self.assertEqual(w["dispensed"], [0] * len(stock))
            self.assertEqual(w["stock_after"], stock)

    def test_objective_basis_recomputes_values(self) -> None:
        basis = self.payload["objectives_basis"]
        obj = self.payload["objectives"]
        self.assertEqual(
            basis["penalty_total"]["value"], obj["penalty_total"]
        )
        self.assertEqual(
            sum(t["value"] for t in basis["initial_cash_used"]["per_cassette"]),
            basis["initial_cash_used"]["value"],
        )
        self.assertEqual(
            basis["initial_cash_used"]["value"], obj["initial_cash_used"]
        )
        terms = basis["transport_reload_cost"]
        expected_cost = (
            terms["transport_cost_per_note"] * terms["initial_notes"]
            + terms["load_cost_per_cassette"] * terms["used_cassettes"]
        )
        self.assertEqual(terms["value"], expected_cost)
        self.assertEqual(terms["value"], obj["transport_reload_cost"])
        self.assertEqual(
            sum(
                t["dispensed_notes"]
                for t in basis["dispensed_notes"]["per_withdrawal"]
            ),
            obj["dispensed_notes"],
        )

    def test_objectives_recomputable_from_raw_input(self) -> None:
        plan = self.payload["plan"]
        basis = self.payload["objectives_basis"]
        penalties = RAW["penalties"]
        failed = basis["penalty_total"]["failed_indices"]
        self.assertEqual(
            sum(penalties[i] for i in failed),
            self.payload["objectives"]["penalty_total"],
        )
        cash = sum(
            f * c
            for f, c in zip(
                plan["denomination_vector"],
                plan["initial_counts_vector"],
            )
        )
        self.assertEqual(cash, self.payload["objectives"]["initial_cash_used"])

    def test_bounds_order_and_optimal_flag(self) -> None:
        self.assertEqual(self.payload["status"], "optimal")
        self.assertTrue(self.payload["optimal"])
        self.assertEqual(
            self.payload["bounds"]["lower_bound"],
            self.payload["bounds"]["upper_bound"],
        )


class CliTest(unittest.TestCase):
    def _run(self, payload: dict | None, raw_text: str | None = None):
        if raw_text is None:
            raw_text = json.dumps(payload)
        proc = subprocess.run(
            [sys.executable, "-m", "atm_optimizer.cli"],
            input=raw_text,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc

    def test_cli_success_canonical_json(self) -> None:
        proc = self._run(RAW)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        decoded = json.loads(proc.stdout)
        self.assertEqual(decoded["status"], "optimal")
        expected = json.dumps(
            decoded, sort_keys=True, indent=2, separators=(",", ": ")
        ) + "\n"
        self.assertEqual(proc.stdout, expected)

    def test_cli_invalid_json_exit_2(self) -> None:
        proc = self._run(None, "{not json")
        self.assertEqual(proc.returncode, 2)
        err = json.loads(proc.stderr)
        self.assertEqual(err["category"], "schema_error")

    def test_cli_validation_category_on_stderr(self) -> None:
        bad = dict(RAW, cassette_count=9)
        proc = self._run(bad)
        self.assertEqual(proc.returncode, 2)
        err = json.loads(proc.stderr)
        self.assertEqual(err["category"], "cassette_count_error")

    def test_cli_budget_incomplete_still_exit_0(self) -> None:
        proc = self._run(dict(RAW, search_budget=10))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        decoded = json.loads(proc.stdout)
        self.assertEqual(decoded["status"], "incomplete")
        self.assertFalse(decoded["optimal"])
        self.assertIn("upper_bound", decoded["bounds"])
        self.assertIn("lower_bound", decoded["bounds"])
        self.assertEqual(decoded["explored_states"], 10)


if __name__ == "__main__":
    unittest.main()
