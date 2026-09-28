"""Canonical, byte-stable JSON serialization of optimizer results.

The output contains the normalized input, the four objective values with
their explicit computation basis (each value recomputable from raw input),
the full replay plan, bounds and search statistics. Serialization sorts object
keys and uses fixed separators/indentation, so equal results produce byte-
identical text regardless of dict insertion order or platform.
"""

from __future__ import annotations

import json
from typing import Any

from .model import Input, Plan, Result


def _normalized_input(inp: Input) -> dict[str, Any]:
    return {
        "cassette_count": inp.cassette_count,
        "cassette_capacity": inp.cassette_capacity,
        "denominations": list(inp.denominations),
        "initial_cash_limit": inp.initial_cash_limit,
        "load_cost_per_cassette": inp.load_cost_per_cassette,
        "penalties": list(inp.penalties),
        "search_budget": inp.search_budget,
        "total_note_limit": inp.total_note_limit,
        "transport_cost_per_note": inp.transport_cost_per_note,
        "withdrawals": list(inp.withdrawals),
    }


def _plan_section(plan: Plan) -> dict[str, Any]:
    return {
        "denomination_vector": list(plan.denomination_vector),
        "initial_counts_vector": list(plan.initial_counts_vector),
        "withdrawals": [
            {
                "amount": outcome.amount,
                "denomination_vector": list(plan.denomination_vector),
                "dispensed": list(outcome.dispensed),
                "index": outcome.index,
                "satisfied": outcome.satisfied,
                "stock_after": list(outcome.stock_after),
                "stock_before": list(outcome.stock_before),
            }
            for outcome in plan.outcomes
        ],
    }


def _objective_basis(inp: Input, plan: Plan) -> dict[str, Any]:
    failed_indices = [o.index for o in plan.outcomes if not o.satisfied]
    penalty_value = sum(inp.penalties[i] for i in failed_indices)
    total_initial_notes = sum(plan.initial_counts_vector)
    used_cassettes = sum(1 for c in plan.initial_counts_vector if c > 0)
    transport_terms = {
        "formula": (
            "transport_cost_per_note * sum_initial_counts + "
            "load_cost_per_cassette * used_cassettes"
        ),
        "initial_notes": total_initial_notes,
        "load_cost_per_cassette": inp.load_cost_per_cassette,
        "transport_cost_per_note": inp.transport_cost_per_note,
        "used_cassettes": used_cassettes,
        "value": (
            total_initial_notes * inp.transport_cost_per_note
            + used_cassettes * inp.load_cost_per_cassette
        ),
    }
    cash_terms = [
        {
            "cassette": i,
            "count": count,
            "denomination": face,
            "value": face * count,
        }
        for i, (face, count) in enumerate(
            zip(plan.denomination_vector, plan.initial_counts_vector)
        )
    ]
    notes_terms = [
        {
            "dispensed_notes": sum(o.dispensed),
            "index": o.index,
            "satisfied": o.satisfied,
        }
        for o in plan.outcomes
    ]
    return {
        "penalty_total": {
            "failed_indices": failed_indices,
            "formula": "sum(penalties[i] for every unsatisfied withdrawal i)",
            "value": penalty_value,
        },
        "transport_reload_cost": transport_terms,
        "initial_cash_used": {
            "formula": "sum(denomination[i] * initial_counts[i])",
            "per_cassette": cash_terms,
            "value": sum(t["value"] for t in cash_terms),
        },
        "dispensed_notes": {
            "formula": "sum over satisfied withdrawals of sum(dispensed)",
            "per_withdrawal": notes_terms,
            "value": sum(t["dispensed_notes"] for t in notes_terms),
        },
    }


def result_to_jsonable(inp: Input, result: Result) -> dict[str, Any]:
    """Build the normalized, fully self-describing output dictionary."""
    plan = result.plan
    objectives = None
    basis = None
    if plan is not None:
        objectives = {
            "penalty_total": plan.objectives.penalty_total,
            "transport_reload_cost": plan.objectives.transport_reload_cost,
            "initial_cash_used": plan.objectives.initial_cash_used,
            "dispensed_notes": plan.objectives.dispensed_notes,
        }
        basis = _objective_basis(inp, plan)
    return {
        "status": result.status,
        "optimal": result.optimal,
        "search_budget": result.budget,
        "explored_states": result.explored_states,
        "bounds": {
            "upper_bound": list(result.upper_bound),
            "lower_bound": list(result.lower_bound),
        },
        "objectives": objectives,
        "objectives_basis": basis,
        "plan": _plan_section(plan) if plan is not None else None,
        "input": _normalized_input(inp),
    }


def dumps_canonical(obj: Any) -> str:
    """Deterministic serialization: sorted keys, fixed formatting, UTF-8."""
    return json.dumps(
        obj,
        ensure_ascii=False,
        indent=2,
        separators=(",", ": "),
        sort_keys=True,
    ) + "\n"
