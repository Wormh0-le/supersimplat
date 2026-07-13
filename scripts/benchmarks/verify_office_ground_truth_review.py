#!/usr/bin/env python3
"""Validate that a Ground Truth review never implies evidence from bad views."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-dir", type=Path, required=True)
    parser.add_argument("--inspection-dir", type=Path, required=True)
    args = parser.parse_args()

    draft = json.loads((args.draft_dir / "ground-truth-draft.json").read_text(encoding="utf-8"))
    review = json.loads((args.inspection_dir / "visual-review.json").read_text(encoding="utf-8"))
    if draft["target_id"] != review["target_id"]:
        raise RuntimeError("draft and visual review target IDs differ")

    review_status = {item["view_id"]: item["status"] for item in review["views"]}
    evidence_views = {item["view_id"] for item in draft["evidence_by_view"]}
    projection_views = {
        item["view_id"]
        for item in draft["projection_review"]["frames"]
        if item.get("projection_status", "rendered") == "rendered"
    }
    violations: list[str] = []
    for view_id, status in review_status.items():
        if status != "insufficient":
            continue
        if view_id in evidence_views:
            violations.append(f"{view_id}: insufficient view is listed as annotation evidence")
        if view_id in projection_views:
            violations.append(f"{view_id}: insufficient view has a labelled projection overlay")

    payload = {
        "target_id": draft["target_id"],
        "status": "pass" if not violations else "fail",
        "violations": violations,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if violations:
        sys.exit(1)


if __name__ == "__main__":
    main()
