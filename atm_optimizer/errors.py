"""Typed error hierarchy for invalid inputs and constraints.

Every error raised for bad user input derives from InputValidationError
so callers can distinguish the concrete failure category instead of catching
a single generic exception.
"""

from __future__ import annotations


class ATMError(Exception):
    """Base class for all errors raised by this package."""


class InputValidationError(ATMError):
    """Base class for every invalid-input category."""

    category: str = "input_error"

    def __init__(self, message: str, *, path: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.path = path

    def to_dict(self) -> dict:
        return {"category": self.category, "message": self.message, "path": self.path}


class SchemaError(InputValidationError):
    """Input is not an object, a field is missing, or has the wrong type."""

    category = "schema_error"


class ValueError_(InputValidationError):
    """A value is negative, zero where positive is required, or out of range."""

    category = "value_error"


class ConstraintError(InputValidationError):
    """Individually valid fields contradict each other (infeasible setup)."""

    category = "constraint_error"


class DenominationError(InputValidationError):
    """Candidate denomination list is empty or otherwise unusable."""

    category = "denomination_error"


class CassetteCountError(InputValidationError):
    """Number of cassettes is outside the supported range [2, 6]."""

    category = "cassette_count_error"


class BudgetError(InputValidationError):
    """The caller-supplied search budget is invalid."""

    category = "budget_error"
