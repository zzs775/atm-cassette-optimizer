"""Per-loading sequence solver: exact set-based dynamic program.

A node at layer t stores the remaining stock per cassette, the action prefix
(one entry per processed request: a dispense tuple or None for failure) and
two cumulative objective components: total business penalty and total dispensed
notes so far.

Dominance (safe pruning): at the same layer, A dominates B iff
  stock_A[i] >= stock_B[i] for every cassette,
  penalty_A <= penalty_B,
  notes_A <= notes_B.
Then any future action sequence feasible from B is feasible from A with
identical future penalties (same future success/failure choices) and no more
future notes, while A is no worse on accumulated objectives. B can never lead
to a strictly better final vector than A.

When A and B are equal on stock, penalty and notes, the canonical action
prefix breaks the tie: the lexicographically larger prefix is dropped
(None sorts before any dispense tuple; tuples compare element-wise). This
keeps exactly one representative per equivalence class, namely the one that
wins the final tie-break. A state is therefore removed only when another
state at the same layer dominates it under the three inequalities above; no
state capable of producing an optimal plan is ever pruned.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .dispense import enumerate_dispenses
from .loading import Loading
from .model import Input

Action = Optional[tuple[int, ...]]

BIG = 10**18

# Reference mode: when False, keep the full frontier (tests only).
DOMINANCE_PRUNING = True


@dataclass
class SequenceResult:
    actions: list[Action]
    penalty_total: int
    dispensed_notes: int


class _Node:
    __slots__ = ("stock", "prefix", "penalty", "notes")

    def __init__(self, stock, prefix, penalty, notes):
        self.stock = stock
        self.prefix = prefix
        self.penalty = penalty
        self.notes = notes


def _action_key(action: Action):
    if action is None:
        return (0, ())
    return (1, action)


def _prefix_lt(a: tuple, b: tuple) -> bool:
    for x, y in zip(a, b):
        kx, ky = _action_key(x), _action_key(y)
        if kx < ky:
            return True
        if kx > ky:
            return False
    return False


def _prefix_key(prefix: tuple):
    return tuple(_action_key(a) for a in prefix)


def _dominates(a: _Node, b: _Node) -> int:
    """Return 1 if a strictly dominates b, 0 if equivalent tie, -1 otherwise."""
    for x, y in zip(a.stock, b.stock):
        if x < y:
            return -1
    if a.penalty > b.penalty or a.notes > b.notes:
        return -1
    if (
        any(x > y for x, y in zip(a.stock, b.stock))
        or a.penalty < b.penalty
        or a.notes < b.notes
    ):
        return 1
    return 0


def _prune(nodes: list[_Node]) -> list[_Node]:
    """Drop dominated nodes; equivalent nodes collapse to smallest prefix."""
    survivors: list[_Node] = []
    n = len(nodes)
    for i in range(n):
        candidate = nodes[i]
        drop = False
        for j in range(n):
            if i == j:
                continue
            other = nodes[j]
            relation = _dominates(other, candidate)
            if relation > 0:
                drop = True
                break
            if relation == 0:
                if _prefix_lt(other.prefix, candidate.prefix) or (
                    other.prefix == candidate.prefix and j < i
                ):
                    drop = True
                    break
        if not drop:
            survivors.append(candidate)
    return survivors


def solve_sequence(
    inp: Input,
    loading: Loading,
    budget: int | None,
    counter: list[int],
    penalty_cutoff: int | None = None,
) -> tuple[SequenceResult | None, bool]:
    """Solve the withdrawal sequence for one fixed loading.

    Each generated node increments the shared counter. Exceeding budget aborts
    immediately with exhausted=True and no result. When penalty_cutoff is
    given, any node whose accumulated penalty exceeds it is never generated:
    such a node cannot end at the cutoff-primary optimum.
    """
    if penalty_cutoff is not None and penalty_cutoff < 0:
        return None, False
    root = _Node(loading.counts, (), 0, 0)
    counter[0] += 1
    if budget is not None and counter[0] >= budget:
        return None, True
    layer = [root]

    for t, amount in enumerate(inp.withdrawals):
        penalty = inp.penalties[t]
        next_layer: list[_Node] = []
        for node in layer:
            for dispensed in enumerate_dispenses(amount, loading.faces, node.stock):
                child = _Node(
                    tuple(s - d for s, d in zip(node.stock, dispensed)),
                    node.prefix + (dispensed,),
                    node.penalty,
                    node.notes + sum(dispensed),
                )
                if (
                    penalty_cutoff is None
                    or child.penalty <= penalty_cutoff
                ):
                    if budget is not None and counter[0] >= budget:
                        return None, True
                    counter[0] += 1
                    next_layer.append(child)
            if penalty_cutoff is None or node.penalty + penalty <= penalty_cutoff:
                if budget is not None and counter[0] >= budget:
                    return None, True
                failed = _Node(
                    node.stock,
                    node.prefix + (None,),
                    node.penalty + penalty,
                    node.notes,
                )
                counter[0] += 1
                next_layer.append(failed)
        layer = _prune(next_layer) if DOMINANCE_PRUNING else next_layer
        if not layer:
            return None, False

    if not layer:
        return None, False
    best = min(layer, key=lambda nd: (nd.penalty, nd.notes, _prefix_key(nd.prefix)))
    return (
        SequenceResult(
            actions=list(best.prefix),
            penalty_total=best.penalty,
            dispensed_notes=best.notes,
        ),
        False,
    )
