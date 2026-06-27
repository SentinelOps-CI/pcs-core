"""Normalize producer BenchmarkCase exports to canonical pcs-core semantics."""

from __future__ import annotations

from typing import Any

from pcs_core.benchmark_compat import _coerce_detection_layer

_SYSTEM_OUTCOME_BY_CASE_KIND: dict[str, str] = {
    "valid_release": "admitted",
    "invalid_certificate": "certificate_rejected",
    "invalid_hash_mismatch": "rejected",
    "invalid_handoff": "rejected",
    "invalid_registry": "rejected",
    "invalid_formal_check": "formal_failed",
    "invalid_import": "import_failed",
    "invalid_render": "render_failed",
    "stale_release": "stale",
}

_STALE_FAILURE_CODES = frozenset(
    {
        "stale_trace_after_certificate",
        "lean_certificate_stale",
    },
)

_CERTIFICATE_REJECT_FAILURE_CODES = frozenset(
    {
        "certificate_id_mismatch",
        "lean_certificate_rejected",
        "rejected_certificate",
    },
)

_PLACEHOLDER_FAILURE_VALUES = frozenset({"", "none", "unknown"})


def _empty_as_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in _PLACEHOLDER_FAILURE_VALUES:
        return None
    return value


def normalize_benchmark_case(
    raw: dict[str, Any],
    *,
    extension: dict[str, Any] | None = None,
    expected_failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Coerce LabTrust/pcs-bench dialect cases without mutating on-disk producer files."""
    case = dict(raw)
    kind = str(case.get("case_kind", ""))

    if kind == "valid_release":
        case["expected_failure_code"] = None
        case["expected_responsible_component"] = None
        case["expected_repair_hint_kind"] = None
    else:
        code = _empty_as_none(case.get("expected_failure_code"))
        if code is None and isinstance(expected_failure, dict):
            code = _empty_as_none(expected_failure.get("expected_failure_code"))
        case["expected_failure_code"] = code
        case["expected_responsible_component"] = _empty_as_none(
            case.get("expected_responsible_component"),
        )
        raw_hint = case.get("expected_repair_hint_kind")
        if raw_hint is None or (
            isinstance(raw_hint, str) and raw_hint.strip().lower() in ("", "none")
        ):
            case["expected_repair_hint_kind"] = None
        else:
            case["expected_repair_hint_kind"] = raw_hint

    if case.get("expected_system_outcome") in (None, ""):
        code = str(case.get("expected_failure_code") or "")
        if code in _STALE_FAILURE_CODES:
            outcome = "stale"
        elif code in _CERTIFICATE_REJECT_FAILURE_CODES:
            outcome = "certificate_rejected"
        elif code.startswith("lean_") or kind == "invalid_formal_check":
            outcome = "formal_failed"
        elif code.startswith("scientific_memory"):
            outcome = "import_failed"
        else:
            outcome = _SYSTEM_OUTCOME_BY_CASE_KIND.get(kind, "unknown")
        case["expected_system_outcome"] = outcome

    layer_source = case.get("expected_detection_layer")
    if layer_source is None and isinstance(extension, dict):
        layer_source = extension.get("expected_detection_layer")
    if layer_source is None and isinstance(expected_failure, dict):
        layer_source = expected_failure.get("expected_detection_layer")
    layer = _coerce_detection_layer(layer_source)
    if layer is not None:
        case["expected_detection_layer"] = layer

    return case
