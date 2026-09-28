"""Input parsing, category-specific validation, and normalization.

Validation errors are split into distinct exception classes (see errors.py):
wrong shape/types raise SchemaError, out-of-range integers raise ValueError_,
contradictory fields raise ConstraintError, unusable denomination lists raise
DenominationError, a bad cassette count raises CassetteCountError and a bad
search budget raises BudgetError. Denominations are deduplicated and sorted
ascending so the optimizer output is independent of their input order.
"""

from __future__ import annotations

from typing import Any

from .errors import (
    BudgetError,
    CassetteCountError,
    ConstraintError,
    DenominationError,
    SchemaError,
    ValueError_,
)
from .model import Input

MIN_CASSETTES = 2
MAX_CASSETTES = 6

_REQUIRED_INT_FIELDS = (
    "cassette_count",
    "cassette_capacity",
    "total_note_limit",
    "initial_cash_limit",
)

_COST_FIELDS = (
    ("transport_cost_per_note", 0),
    ("load_cost_per_cassette", 0),
)


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _as_nonneg_int(value: Any, path: str, *, positive: bool = False) -> int:
    if _is_bool(value) or not isinstance(value, int):
        raise SchemaError("expected an integer", path=path)
    if value < 0:
        raise ValueError_("value must be non-negative", path=path)
    if positive and value == 0:
        raise ValueError_("value must be strictly positive", path=path)
    return value


def _as_int_list(value: Any, path: str) -> list[int]:
    if not isinstance(value, list):
        raise SchemaError("expected a list of integers", path=path)
    result: list[int] = []
    for i, item in enumerate(value):
        item_path = f"{path}[{i}]"
        if _is_bool(item) or not isinstance(item, int):
            raise SchemaError("expected an integer", path=item_path)
        result.append(item)
    return result


def parse_input(raw: Any) -> Input:
    """Validate a decoded JSON object and return a normalized Input.

    Required fields: cassette_count, denominations, cassette_capacity,
    total_note_limit, initial_cash_limit, withdrawals, penalties.
    Optional fields: transport_cost_per_note (default 0),
    load_cost_per_cassette (default 0), search_budget (default None).
    """
    if not isinstance(raw, dict):
        raise SchemaError("top-level input must be a JSON object")

    for name in _REQUIRED_INT_FIELDS:
        if name not in raw:
            raise SchemaError(f"missing required field: {name}", path=name)
    for name in ("withdrawals", "penalties", "denominations"):
        if name not in raw:
            raise SchemaError(f"missing required field: {name}", path=name)

    cassette_count = _as_nonneg_int(raw["cassette_count"], "cassette_count")
    if not (MIN_CASSETTES <= cassette_count <= MAX_CASSETTES):
        raise CassetteCountError(
            f"cassette_count must be in [{MIN_CASSETTES}, {MAX_CASSETTES}]"
        )

    cassette_capacity = _as_nonneg_int(
        raw["cassette_capacity"], "cassette_capacity", positive=True
    )
    total_note_limit = _as_nonneg_int(
        raw["total_note_limit"], "total_note_limit", positive=True
    )
    initial_cash_limit = _as_nonneg_int(
        raw["initial_cash_limit"], "initial_cash_limit"
    )

    raw_denominations = _as_int_list(raw["denominations"], "denominations")
    for i, denomination in enumerate(raw_denominations):
        if denomination < 0:
            raise ValueError_(
                "denominations must be non-negative",
                path=f"denominations[{i}]",
            )
    denominations = tuple(sorted(set(raw_denominations)))
    if not denominations:
        raise DenominationError("denominations must contain at least one value")
    if denominations[0] <= 0:
        raise DenominationError(
            "denominations must be positive (zero is not a valid denomination)",
            path="denominations",
        )

    withdrawals_list = _as_int_list(raw["withdrawals"], "withdrawals")
    for i, amount in enumerate(withdrawals_list):
        if amount < 0:
            raise ValueError_(
                "withdrawal amounts must be non-negative",
                path=f"withdrawals[{i}]",
            )

    penalties_list = _as_int_list(raw["penalties"], "penalties")
    for i, penalty in enumerate(penalties_list):
        if penalty < 0:
            raise ValueError_(
                "penalties must be non-negative",
                path=f"penalties[{i}]",
            )
    if len(penalties_list) != len(withdrawals_list):
        raise ConstraintError(
            "penalties must have the same length as withdrawals",
            path="penalties",
        )

    costs: dict[str, int] = {}
    for name, default in _COST_FIELDS:
        if name in raw and raw[name] is not None:
            costs[name] = _as_nonneg_int(raw[name], name)
        else:
            costs[name] = default

    search_budget: int | None = None
    if "search_budget" in raw and raw["search_budget"] is not None:
        budget_value = raw["search_budget"]
        if _is_bool(budget_value) or not isinstance(budget_value, int):
            raise BudgetError("search_budget must be a positive integer or null")
        if budget_value <= 0:
            raise BudgetError("search_budget must be strictly positive")
        search_budget = budget_value

    if total_note_limit > cassette_count * cassette_capacity:
        raise ConstraintError(
            "total_note_limit exceeds cassette_count * cassette_capacity"
        )

    return Input(
        cassette_count=cassette_count,
        denominations=denominations,
        cassette_capacity=cassette_capacity,
        total_note_limit=total_note_limit,
        initial_cash_limit=initial_cash_limit,
        withdrawals=tuple(withdrawals_list),
        penalties=tuple(penalties_list),
        transport_cost_per_note=costs["transport_cost_per_note"],
        load_cost_per_cassette=costs["load_cost_per_cassette"],
        search_budget=search_budget,
    )
