"""Run the operator-only real-input diagnostic for issue #115."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from selection_service_companion.issue_115_bonsai_runner import (
    DEFAULT_S0_COMPARISON_BUDGET,
    Issue115BonsaiRunBlocked,
    run_issue_115_bonsai_diagnostics,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run-issue-115-bonsai")
    parser.add_argument(
        "--input-directory",
        type=Path,
        default=Path("data/issue-115-bonsai"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--max-s0-comparisons",
        type=int,
        default=DEFAULT_S0_COMPARISON_BUDGET,
        help="protect the scalar S0/Scope componentizers; zero means no guard",
    )
    arguments = parser.parse_args(argv)
    if arguments.max_s0_comparisons < 0:
        parser.error("--max-s0-comparisons must be non-negative")
    try:
        result = run_issue_115_bonsai_diagnostics(
            input_directory=arguments.input_directory,
            max_s0_comparisons=arguments.max_s0_comparisons,
        )
    except Issue115BonsaiRunBlocked as error:
        result = {
            "status": "blocked",
            "diagnosticKind": "issue-115-bonsai-3d-diagnostics/v1",
            "stage": error.stage,
            "message": str(error),
            "details": error.details,
        }
        print(f"#115 diagnostic blocked at {error.stage}: {error}", file=sys.stderr)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return 2
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"#115 diagnostic complete: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
