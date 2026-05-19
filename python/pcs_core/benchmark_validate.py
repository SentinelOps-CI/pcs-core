"""Semantic validation for benchmark protocol artifacts."""

from __future__ import annotations

from typing import Any

from pcs_core.benchmark_localization import FAILURE_CODE_TO_COMPONENT
from pcs_core.benchmark_registry_data import benchmark_suite_entries


KNOWN_CASE_KINDS = frozenset(
    {
        "valid_release",
        "invalid_hash_mismatch",
        "invalid_certificate",
        "invalid_handoff",
        "invalid_registry",
        "invalid_formal_check",
        "invalid_import",
        "invalid_render",
        "stale_release",
    },
)


def validate_benchmark_task_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    metrics = data.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        errors.append("BenchmarkTask.v0 requires non-empty metrics")
    return errors


def validate_benchmark_case_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    kind = data.get("case_kind")
    if kind not in KNOWN_CASE_KINDS:
        errors.append(f"BenchmarkCase.v0 unknown case_kind {kind!r}")
    if kind == "valid_release":
        if data.get("expected_status") != "passed":
            errors.append("valid_release cases must expect passed status")
        if data.get("expected_failure_code"):
            errors.append("valid_release cases must have empty expected_failure_code")
    else:
        if not data.get("expected_failure_code"):
            errors.append("invalid cases require expected_failure_code")
    code = data.get("expected_failure_code")
    if isinstance(code, str) and code and code not in FAILURE_CODE_TO_COMPONENT:
        errors.append(
            f"expected_failure_code {code!r} not in benchmark localization catalog",
        )
    return errors


def validate_benchmark_registry_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    catalog = benchmark_suite_entries()
    suites = data.get("suites")
    if not isinstance(suites, dict):
        return ["BenchmarkRegistry.v0 suites must be an object"]
    if set(suites) != set(catalog):
        errors.append(
            f"suite keys drift from catalog (on_disk={sorted(suites)} catalog={sorted(catalog)})",
        )
    return errors
