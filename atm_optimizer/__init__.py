"""ATM cassette loading and dispense optimizer (standard library only)."""

from .errors import ATMError
from .model import Input, Result
from .planner import optimize

__all__ = ["ATMError", "Input", "Result", "optimize"]
__version__ = "0.1.0"
