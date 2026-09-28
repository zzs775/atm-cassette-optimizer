"""Category-specific input validation tests."""

from __future__ import annotations

import unittest

from atm_optimizer.errors import (
    BudgetError,
    CassetteCountError,
    ConstraintError,
    DenominationError,
    SchemaError,
    ValueError_,
)
from atm_optimizer.validate import parse_input

BASE = {
    "cassette_count": 3,
    "denominations": [10, 20, 50],
    "cassette_capacity": 20,
    "total_note_limit": 40,
    "initial_cash_limit": 2000,
    "withdrawals": [60, 40],
    "penalties": [100, 100],
}


class ValidationTest(unittest.TestCase):
    def _base(self) -> dict:
        return dict(BASE)

    def test_ok_normalizes_denomination_order_and_duplicates(self) -> None:
        raw = self._base()
        raw["denominations"] = [50, 10, 20, 10]
        inp = parse_input(raw)
        self.assertEqual(inp.denominations, (10, 20, 50))

    def test_not_object_is_schema_error(self) -> None:
        with self.assertRaises(SchemaError):
            parse_input([1, 2, 3])

    def test_missing_field_is_schema_error(self) -> None:
        raw = self._base()
        del raw["withdrawals"]
        with self.assertRaises(SchemaError):
            parse_input(raw)

    def test_wrong_type_is_schema_error(self) -> None:
        raw = self._base()
        raw["cassette_capacity"] = "20"
        with self.assertRaises(SchemaError):
            parse_input(raw)

    def test_bool_is_not_int(self) -> None:
        raw = self._base()
        raw["cassette_count"] = True
        with self.assertRaises(SchemaError):
            parse_input(raw)

    def test_bad_cassette_count(self) -> None:
        for bad in (1, 7):
            raw = self._base()
            raw["cassette_count"] = bad
            with self.assertRaises(CassetteCountError):
                parse_input(raw)

    def test_negative_value(self) -> None:
        raw = self._base()
        raw["withdrawals"] = [-1, 10]
        with self.assertRaises(ValueError_):
            parse_input(raw)

    def test_zero_capacity(self) -> None:
        raw = self._base()
        raw["cassette_capacity"] = 0
        with self.assertRaises(ValueError_):
            parse_input(raw)

    def test_empty_and_zero_denominations(self) -> None:
        raw = self._base()
        raw["denominations"] = []
        with self.assertRaises(DenominationError):
            parse_input(raw)
        raw = self._base()
        raw["denominations"] = [0, 10]
        with self.assertRaises(DenominationError):
            parse_input(raw)

    def test_penalty_length_mismatch(self) -> None:
        raw = self._base()
        raw["penalties"] = [1]
        with self.assertRaises(ConstraintError):
            parse_input(raw)

    def test_note_limit_above_physical_capacity(self) -> None:
        raw = self._base()
        raw["cassette_count"] = 2
        raw["cassette_capacity"] = 5
        raw["total_note_limit"] = 11
        with self.assertRaises(ConstraintError):
            parse_input(raw)

    def test_bad_budget(self) -> None:
        raw = self._base()
        raw["search_budget"] = 0
        with self.assertRaises(BudgetError):
            parse_input(raw)
        raw = self._base()
        raw["search_budget"] = -3
        with self.assertRaises(BudgetError):
            parse_input(raw)

    def test_default_costs_and_budget(self) -> None:
        inp = parse_input(self._base())
        self.assertEqual(inp.transport_cost_per_note, 0)
        self.assertEqual(inp.load_cost_per_cassette, 0)
        self.assertIsNone(inp.search_budget)


if __name__ == "__main__":
    unittest.main()
