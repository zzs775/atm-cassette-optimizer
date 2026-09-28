"""Exact nested optimizer: loading plus per-request dispense, jointly planned.

Phases
------
Phase 1 streams every feasible loading in canonical order (face vector, then
counts vector) and solves its withdrawal sequence exactly, tracking the best
penalty P* and simultaneously a proven lower bound C0 on initial cash: the
maximum single-withdrawal amount is itself a lower bound on the cash any
satisfying plan must carry (notes are never moved into the machine later).

Phase 2 re-streams the loadings and solves only those whose penalty can equal
P*, pruning by the four-level objective:
  * cash below C0 cannot satisfy all requests (skipped already in phase 1
    for the bound value, and again in phase 2 when P* needs all satisfied);
  * cost strictly above the incumbent cannot win (cost is monotone non-
    decreasing as counts grow, so a partial count vector already over the
    bound can be pruned safely);
  * at equal cost, cash above the incumbent cannot win.
The tie-break vectors (face vector, counts vector, dispense prefix) come for
free from canonical enumeration order, so the first best plan is canonical.

Budget: explored_states counts every generated sequence-DP node; the two
loading roots of a loading that is solved in both phases are counted as
distinct explored states. Exhaustion returns the incumbent with proven lower
bound and optimal=False.
"""

from __future__ import annotations

from .loading import LoadBound, Loading, iter_loadings
from .model import Input, Objectives, Plan, Result, WithdrawalOutcome
from .sequence import SequenceResult, solve_sequence

BIG = 10**18

# Reference mode: disable loading-level branch-and-bound (used by tests).
BRANCH_AND_BOUND = True


def _loading_cost(loading: Loading, inp: Input) -> int:
    notes_cost = loading.notes * inp.transport_cost_per_note
    cassette_cost = loading.used_cassettes * inp.load_cost_per_cassette
    return notes_cost + cassette_cost


def _objective_vector(
    seq: SequenceResult, loading: Loading, inp: Input
) -> tuple[int, int, int, int]:
    return (
        seq.penalty_total,
        _loading_cost(loading, inp),
        loading.cash,
        seq.dispensed_notes,
    )


def _loading_cost(loading: Loading, inp: Input) -> int:
    notes_cost = loading.notes * inp.transport_cost_per_note
    cassette_cost = loading.used_cassettes * inp.load_cost_per_cassette
    return notes_cost + cassette_cost


def _relaxation_lower_bound(inp: Input) -> tuple[int, int, int, int]:
    """Provable lower bound vector from unconstrained relaxations.

    Level 1: a request must fail in every plan when its amount is not
    reachable as a non-negative combination of candidate denominations using
    at most total_note_limit notes (note-count coin change; per-cassette
    capacity and sequence coupling are relaxed away).
    Levels 2..4: zero is a universally valid component lower bound.
    """
    reachable = {0}
    frontier = {0}
    for _ in range(inp.total_note_limit):
        nxt = {
            value + face
            for value in frontier
            for face in inp.denominations
        }
        frontier = nxt - reachable
        reachable |= frontier
    forced_penalty = 0
    for amount, penalty in zip(inp.withdrawals, inp.penalties):
        if amount not in reachable:
            forced_penalty += penalty
    return (forced_penalty, 0, 0, 0)


def _build_plan(
    inp: Input,
    loading: Loading,
    seq: SequenceResult,
    obj: tuple[int, int, int, int],
) -> Plan:
    outcomes: list[WithdrawalOutcome] = []
    stock = loading.counts
    for t, action in enumerate(seq.actions):
        amount = inp.withdrawals[t]
        stock_before = stock
        if action is None:
            satisfied = False
            dispensed = tuple(0 for _ in stock)
            stock_after = stock
        else:
            satisfied = True
            dispensed = action
            stock_after = tuple(
                s - d for s, d in zip(stock, dispensed)
            )
        outcomes.append(
            WithdrawalOutcome(
                index=t,
                amount=amount,
                satisfied=satisfied,
                dispensed=dispensed,
                stock_before=stock_before,
                stock_after=stock_after,
            )
        )
        stock = stock_after
    return Plan(
        denomination_vector=loading.faces,
        initial_counts_vector=loading.counts,
        outcomes=tuple(outcomes),
        objectives=Objectives(
            penalty_total=obj[0],
            transport_reload_cost=obj[1],
            initial_cash_used=obj[2],
            dispensed_notes=obj[3],
        ),
    )


def optimize(inp: Input) -> Result:
    """Solve the full nested optimization exactly, honoring search_budget.

    Streams loadings once, in canonical order. While the minimum penalty P* is
    unproven only the penalty level prunes. Once P* matches the relaxation's
    forced-penalty lower bound it is proven; from that loading onward the
    LoadBound also prunes by cost and cash against the incumbent. The first
    loading achieving the best (P*, cost, cash, notes) wins every tie-break
    because enumeration and per-loading prefix choice are both canonical.
    """
    relaxation = _relaxation_lower_bound(inp)
    forced_penalty = relaxation[0]

    must_satisfy_cash = 0
    reachable = _reachable_amounts(inp)
    for amount, penalty in zip(inp.withdrawals, inp.penalties):
        if amount > 0 and penalty > 0 and amount not in reachable:
            pass
        elif penalty > 0:
            must_satisfy_cash += amount

    bound = LoadBound(min_cash_needed=0) if BRANCH_AND_BOUND else None
    counter = [0]
    best_vector: tuple[int, int, int, int] | None = None
    best_plan: Plan | None = None
    proven_primary = False
    exhausted = False

    for loading in iter_loadings(inp, bound):
        if inp.search_budget is not None and counter[0] >= inp.search_budget:
            exhausted = True
            break
        cutoff = best_vector[0] if best_vector is not None else None
        seq, loading_exhausted = solve_sequence(
            inp, loading, inp.search_budget, counter, cutoff
        )
        if loading_exhausted:
            exhausted = True
            break
        if seq is None:
            continue
        vector = _objective_vector(seq, loading, inp)
        if best_vector is None or vector < best_vector:
            best_vector = vector
            best_plan = _build_plan(inp, loading, seq, vector)
            if not proven_primary and best_vector[0] <= forced_penalty:
                proven_primary = True
        if proven_primary and bound is not None:
            bound.best_cost = best_vector[1]
            bound.best_cash = best_vector[2]
            bound.min_cash_needed = (
                must_satisfy_cash if best_vector[0] == forced_penalty else 0
            )

    lower_bound = relaxation
    if best_vector is None:
        upper: tuple[int, int, int, int] = (BIG, BIG, BIG, BIG)
    else:
        upper = best_vector
        if not exhausted:
            lower_bound = best_vector
    if best_plan is not None and not exhausted:
        status = "optimal"
        optimal = True
    else:
        status = "incomplete"
        optimal = False
    return Result(
        status=status,
        optimal=optimal,
        plan=best_plan,
        upper_bound=upper,
        lower_bound=lower_bound,
        explored_states=counter[0],
        budget=inp.search_budget,
    )


def _reachable_amounts(inp: Input) -> set[int]:
    """Amounts payable by <= total_note_limit candidate notes (relaxation)."""
    reachable = {0}
    frontier = {0}
    for _ in range(inp.total_note_limit):
        nxt = {
            value + face
            for value in frontier
            for face in inp.denominations
        }
        frontier = nxt - reachable
        if not frontier:
            break
        reachable |= frontier
    return reachable
