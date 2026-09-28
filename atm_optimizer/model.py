"""Core immutable data types for the ATM optimizer.

The objects here are plain frozen dataclasses holding normalized
(input-order-independent) content so that downstream planning is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Input:
    """Validated, normalized optimization input."""

    cassette_count: int
    denominations: tuple[int, ...]
    cassette_capacity: int
    total_note_limit: int
    initial_cash_limit: int
    withdrawals: tuple[int, ...]
    penalties: tuple[int, ...]
    transport_cost_per_note: int
    load_cost_per_cassette: int
    search_budget: Optional[int] = None


@dataclass(frozen=True)
class WithdrawalOutcome:
    """Replay record for a single withdrawal request."""

    index: int
    amount: int
    satisfied: bool
    dispensed: tuple[int, ...]
    stock_before: tuple[int, ...]
    stock_after: tuple[int, ...]


@dataclass(frozen=True)
class Objectives:
    """The four strictly-lexicographic objective levels."""

    penalty_total: int
    transport_reload_cost: int
    initial_cash_used: int
    dispensed_notes: int


@dataclass(frozen=True)
class Plan:
    """One fully-specified, replayable solution."""

    denomination_vector: tuple[int, ...]
    initial_counts_vector: tuple[int, ...]
    outcomes: tuple[WithdrawalOutcome, ...]
    objectives: Objectives


@dataclass(frozen=True)
class Result:
    """Optimizer result; optimal is False only when the budget ran out."""

    status: str
    optimal: bool
    plan: Optional[Plan]
    upper_bound: tuple[int, int, int, int]
    lower_bound: tuple[int, int, int, int]
    explored_states: int
    budget: Optional[int] = None


def empty_stub() -> None:
    """Skeleton placeholder, removed during implementation phase."""
    raise NotImplementedError
