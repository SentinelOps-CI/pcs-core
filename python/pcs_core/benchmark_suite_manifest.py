"""Load suite manifests co-located with benchmark fixture trees."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_benchmark_manifest(fixture_root: Path) -> dict[str, Any] | None:
    path = fixture_root / "benchmark_manifest.v0.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def manifest_case_lists(manifest: dict[str, Any]) -> tuple[list[str], list[str], str | None]:
    """Return (valid_case_ids, invalid_case_ids, workflow_id)."""
    workflow_id = manifest.get("workflow_id")
    if not isinstance(workflow_id, str):
        suite_id = manifest.get("suite_id")
        workflow_id = str(suite_id) if suite_id else None

    valid_cases: list[str] = []
    invalid_cases: list[str] = []
    for entry in manifest.get("cases", []):
        if not isinstance(entry, dict):
            continue
        case_id = str(entry.get("case_id", ""))
        if not case_id:
            continue
        polarity = str(entry.get("polarity", ""))
        if polarity == "valid":
            valid_cases.append(case_id)
        elif polarity == "invalid":
            invalid_cases.append(case_id)

    if not valid_cases and isinstance(manifest.get("valid_cases"), list):
        valid_cases = [str(item) for item in manifest["valid_cases"]]
    if not invalid_cases and isinstance(manifest.get("invalid_cases"), list):
        invalid_cases = [str(item) for item in manifest["invalid_cases"]]

    return valid_cases, invalid_cases, workflow_id


def registry_matches_manifest(
    suite_entry: dict[str, Any],
    manifest: dict[str, Any],
    *,
    suite_id: str | None = None,
) -> list[str]:
    """Return errors when BenchmarkRegistry.v0 suite entry drifts from benchmark_manifest.v0.json."""
    errors: list[str] = []
    manifest_suite = manifest.get("suite_id")
    if manifest_suite and suite_id and str(manifest_suite) != suite_id:
        return errors

    manifest_valid, manifest_invalid, workflow_id = manifest_case_lists(manifest)
    if workflow_id and workflow_id not in suite_entry.get("workflow_ids", []):
        errors.append(
            f"workflow_id {workflow_id!r} missing from registry workflow_ids",
        )
    reg_valid = set(suite_entry.get("valid_cases", []))
    reg_invalid = set(suite_entry.get("invalid_cases", []))
    if set(manifest_valid) != reg_valid:
        errors.append(
            f"valid_cases drift (manifest={sorted(manifest_valid)} registry={sorted(reg_valid)})",
        )
    if set(manifest_invalid) != reg_invalid:
        errors.append(
            f"invalid_cases drift (manifest={sorted(manifest_invalid)} registry={sorted(reg_invalid)})",
        )
    return errors
