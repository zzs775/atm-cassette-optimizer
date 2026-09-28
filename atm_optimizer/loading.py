"""Feasible loading-configuration enumeration.

A loading pairs a non-decreasing denomination vector (candidate denominations
plus a 0 sentinel for unused cassettes) with an initial note count per
cassette. iter_loadings streams loadings in canonical order: denomination
vector ascending (0 first), then counts vector ascending per position.

Branch and bound: a bound object (planner.BoundState) may provide
current best cost/cash and the minimum cash required to satisfy the sequence;
face-vector and count prefixes whose minimum possible cost/cash already
exceed the bound are skipped. Skipping is safe for the secondary objectives
only when the incumbent already matches the proven primary optimum; callers
hand it None until that stage is reached.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

from .model import Input

UNUSED = 0


@dataclass(frozen=True)
class Loading:
    faces: tuple[int, ...]
    counts: tuple[int, ...]
    cash: int
    notes: int
    used_cassettes: int


@dataclass
class LoadBound:
    """Mutable pruning bound shared with the planner while streaming."""

    best_cost: Optional[int] = None
    best_cash: Optional[int] = None
    min_cash_needed: int = 0


def enumerate_loadings(inp: Input) -> list[Loading]:
    """Return every feasible loading in canonical ascending order."""
    return list(iter_loadings(inp, None))


def iter_loadings(
    inp: Input, bound: Optional[LoadBound] = None
) -> Iterator[Loading]:
    """Yield feasible loadings in canonical order with optional pruning."""
    k = inp.cassette_count
    face_choices = (UNUSED,) + tuple(inp.denominations)
    face_vec = [0] * k
    count_vec = [0] * k

    def gen_counts(
        pos: int, used: int, total_notes: int, total_cash: int, min_cash: int
    ) -> Iterator[Loading]:
        if pos == k:
            if total_cash < min_cash:
                return
            yield Loading(
                tuple(face_vec), tuple(count_vec), total_cash, total_notes, used
            )
            return
        face = face_vec[pos]
        if face == UNUSED:
            count_vec[pos] = 0
            yield from gen_counts(
                pos + 1, used, total_notes, total_cash, min_cash
            )
            return
        max_count = min(
            inp.cassette_capacity,
            inp.total_note_limit - total_notes,
        )
        if face > 0:
            max_count = min(
                max_count, (inp.initial_cash_limit - total_cash) // face
            )
        if max_count < 0:
            return
        for count in range(max_count + 1):
            count_vec[pos] = count
            new_cash = total_cash + count * face
            new_used = used + (1 if count > 0 else 0)
            if bound is not None and bound.best_cost is not None:
                # Partial cost/cash through this position; later cassettes can
                # only add non-negative amounts to both, so pruning here is safe.
                partial_cost = (
                    (total_notes + count) * inp.transport_cost_per_note
                    + new_used * inp.load_cost_per_cassette
                )
                partial_cash = new_cash
                if partial_cost > bound.best_cost:
                    continue
                if (
                    partial_cost == bound.best_cost
                    and partial_cash > bound.best_cash
                ):
                    continue
            yield from gen_counts(
                pos + 1,
                new_used,
                total_notes + count,
                new_cash,
                min_cash,
            )
        count_vec[pos] = 0

    def gen_faces(pos: int, prev_idx: int) -> Iterator[Loading]:
        if pos == k:
            min_cash = bound.min_cash_needed if bound is not None else 0
            yield from gen_counts(0, 0, 0, 0, min_cash)
            return
        for idx in range(prev_idx, len(face_choices)):
            face_vec[pos] = face_choices[idx]
            yield from gen_faces(pos + 1, idx)
        face_vec[pos] = 0

    yield from gen_faces(0, 0)
