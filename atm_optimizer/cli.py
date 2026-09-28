"""Command line entry point.

Read a JSON problem description from a file path argument or standard input,
validate it, run the exact optimizer and write canonical JSON to standard
output. Validation errors are emitted on standard error as canonical JSON
(category + message + path) and yield exit code 2; malformed JSON yields the
schema_error category as well. Budget exhaustion is not an error: status is
"incomplete" with optimal=false and exit code 0.
"""

from __future__ import annotations

import json
import sys
from typing import Sequence

from .errors import ATMError, SchemaError
from .planner import optimize
from .protocol import dumps_canonical, result_to_jsonable
from .validate import parse_input


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1:
        sys.stderr.write("usage: atm-optimizer [input.json]\n")
        return 64
    try:
        if len(args) == 1:
            with open(args[0], "r", encoding="utf-8") as handle:
                text = handle.read()
        else:
            text = sys.stdin.read()
    except OSError as exc:
        _emit_error(SchemaError(f"cannot read input: {exc}"))
        return 2

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        _emit_error(SchemaError(f"invalid JSON: {exc.msg}", path=str(exc.pos)))
        return 2

    try:
        inp = parse_input(raw)
    except ATMError as exc:
        _emit_error(exc)
        return 2

    result = optimize(inp)
    payload = result_to_jsonable(inp, result)
    sys.stdout.write(dumps_canonical(payload))
    return 0


def _emit_error(exc: ATMError) -> None:
    if hasattr(exc, "to_dict"):
        payload = exc.to_dict()
    else:
        payload = {"category": "internal_error", "message": str(exc), "path": ""}
    sys.stderr.write(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
