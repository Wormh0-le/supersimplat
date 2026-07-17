#!/usr/bin/env python3
"""Run or independently score the production controlled-overlap PoC Trial."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMPANION_SOURCE = REPOSITORY_ROOT / "selection-service-companion" / "src"
sys.path.insert(0, str(COMPANION_SOURCE))

from selection_service_companion.benchmark import score_prediction  # noqa: E402
from selection_service_companion.controlled_overlap_benchmark import (  # noqa: E402
    run_controlled_overlap_prediction,
)
from selection_service_companion.state import DEFAULT_STATE_DIRECTORY  # noqa: E402


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    commands = result.add_subparsers(dest="command", required=True)

    predict = commands.add_parser("predict")
    predict.add_argument("--output", type=Path, required=True)
    predict.add_argument(
        "--fixture-ply",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "docs/benchmarks/fixtures/controlled-overlap/controlled_front_back_overlap.ply"
        ),
    )
    predict.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIRECTORY)
    predict.add_argument("--model-manifest-digest")
    predict.add_argument("--image-size", type=int, default=1008)
    predict.add_argument("--seed", default="controlled-overlap-seed-1")
    predict.add_argument(
        "--prompt-log",
        type=Path,
        default=None,
        help=(
            "frozen blind Benchmark Prompt Log; defaults to the fixture's "
            "benchmark-prompt-log-v1.json"
        ),
    )

    score = commands.add_parser("score")
    score.add_argument("--prediction", type=Path, required=True)
    score.add_argument("--ground-truth", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    return result


def main() -> int:
    arguments = parser().parse_args()
    if arguments.command == "predict":
        record = run_controlled_overlap_prediction(
            arguments.output,
            fixture_ply=arguments.fixture_ply,
            state_directory=arguments.state_dir,
            model_manifest_digest=arguments.model_manifest_digest,
            image_size=arguments.image_size,
            deterministic_seed=arguments.seed,
            prompt_log_path=arguments.prompt_log,
        )
        manifest = json.loads(record.manifest_path.read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "prediction": str(record.directory),
                    "seal": record.manifest_sha256,
                    "status": manifest["status"],
                    "terminalState": manifest["bindings"]["terminalState"],
                }
            )
        )
        return 0 if manifest["status"] == "prediction-complete" else 2

    result = score_prediction(
        arguments.prediction,
        ground_truth_path=arguments.ground_truth,
        output_path=arguments.output,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
