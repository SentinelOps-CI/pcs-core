"""Semantic validation for benchmark protocol artifacts."""

from __future__ import annotations

from typing import Any

from pcs_core.benchmark_localization import FAILURE_CODE_TO_COMPONENT
from pcs_core.benchmark_metric_registry_data import benchmark_metric_entries
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
        outcome = data.get("expected_system_outcome")
        if outcome is not None and outcome != "admitted":
            errors.append("valid_release cases must expect admitted system outcome when set")
        for field in (
            "expected_failure_code",
            "expected_responsible_component",
            "expected_repair_hint_kind",
        ):
            value = data.get(field)
            if value not in (None, "", "none", "unknown"):
                errors.append(f"valid_release cases must have null {field}")
    else:
        if not data.get("expected_failure_code"):
            errors.append("invalid cases require expected_failure_code")
        if data.get("expected_responsible_component") is None:
            errors.append("invalid cases require expected_responsible_component")
        if data.get("expected_repair_hint_kind") is None:
            errors.append("invalid cases require expected_repair_hint_kind")
    code = data.get("expected_failure_code")
    if isinstance(code, str) and code and code not in FAILURE_CODE_TO_COMPONENT:
        errors.append(
            f"expected_failure_code {code!r} not in benchmark localization catalog",
        )
    return errors


def validate_benchmark_run_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = data.get("observed_status")
    if status == "passed":
        for field in (
            "observed_failure_code",
            "observed_responsible_component",
            "observed_repair_hint",
        ):
            if data.get(field) not in (None, ""):
                errors.append(f"passed runs must have null {field}")
    return errors


def validate_benchmark_report_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    metrics = data.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        errors.append("BenchmarkReport.v0 requires non-empty metrics (metric IDs)")
        return errors
    catalog = benchmark_metric_entries()
    for metric_id in metrics:
        if metric_id not in catalog:
            errors.append(f"BenchmarkReport.v0 unknown metric_id {metric_id!r}")
    summaries = data.get("metric_summaries")
    if not isinstance(summaries, list):
        errors.append("BenchmarkReport.v0 requires metric_summaries array")
        return errors
    summary_ids = {row.get("metric_id") for row in summaries if isinstance(row, dict)}
    for metric_id in metrics:
        if metric_id not in summary_ids:
            errors.append(f"BenchmarkReport.v0 missing MetricSummary for {metric_id!r}")
    for index, row in enumerate(summaries):
        if not isinstance(row, dict):
            errors.append(f"metric_summaries[{index}] must be an object")
            continue
        row_metric = row.get("metric_id")
        if row_metric not in catalog:
            errors.append(f"metric_summaries[{index}] unknown metric_id {row_metric!r}")
        if row_metric in metrics and row.get("applicability") == "measured":
            score = row.get("score")
            if not isinstance(score, (int, float)) or score < 0 or score > 1:
                errors.append(f"metric_summaries[{index}] measured score must be in [0, 1]")
    return errors


PRODUCER_EMBEDDED_REF_FIELDS: dict[str, tuple[str, ...]] = {
    "labtrust-gym": ("benchmark_runs",),
    "certifyedge": ("coverage_reports",),
    "provability-fabric": ("explain_quality_reports", "profile_coverage_reports"),
    "scientific-memory": ("explain_quality_reports",),
}


def validate_benchmark_artifact_ref_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    from pcs_core.benchmark_compat import INGEST_EMBEDDED_ARRAYS

    artifact_type = data.get("artifact_type")
    if artifact_type not in INGEST_EMBEDDED_ARRAYS:
        errors.append(f"BenchmarkArtifactRef.v0 unsupported artifact_type {artifact_type!r}")
    path = data.get("path")
    if not isinstance(path, str) or not path.strip():
        errors.append("BenchmarkArtifactRef.v0 path must be non-empty")
    sha256 = data.get("sha256")
    if isinstance(sha256, str) and not sha256.startswith("sha256:"):
        errors.append("BenchmarkArtifactRef.v0 sha256 must be a sha256: hex digest")
    return errors


def _embedded_ingest_objects(data: dict[str, Any], artifact_type: str) -> list[dict[str, Any]]:
    from pcs_core.benchmark_compat import INGEST_EMBEDDED_ARRAYS

    field = INGEST_EMBEDDED_ARRAYS.get(artifact_type)
    if field is None:
        return []
    rows = data.get(field)
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def validate_pcs_bench_ingest_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    producer_id = data.get("producer_id")
    allowed_producers = {
        "pcs-core",
        "pcs-bench",
        "labtrust-gym",
        "certifyedge",
        "provability-fabric",
        "scientific-memory",
    }
    if producer_id not in allowed_producers:
        errors.append(f"PcsBenchIngest.v0 unknown producer_id {producer_id!r}")
    for field in (
        "benchmark_runs",
        "coverage_reports",
        "failure_localization_reports",
        "explain_quality_reports",
        "profile_coverage_reports",
        "commands",
        "logs",
    ):
        if not isinstance(data.get(field), list):
            errors.append(f"PcsBenchIngest.v0 requires list {field}")
    from pcs_core.benchmark_compat import INGEST_EMBEDDED_ARRAYS

    producer_fields = PRODUCER_EMBEDDED_REF_FIELDS.get(str(producer_id), ())
    has_producer_embedded = any(
        isinstance(data.get(field), list) and len(data.get(field)) > 0
        for field in producer_fields
    )
    refs = data.get("artifact_refs")
    if has_producer_embedded and refs is None:
        errors.append(
            f"PcsBenchIngest.v0 producer {producer_id!r} requires artifact_refs "
            "when exporting embedded artifacts",
        )
        return errors
    if refs is None:
        return errors
    if not isinstance(refs, list):
        errors.append("PcsBenchIngest.v0 artifact_refs must be an array when present")
        return errors
    paths: list[str] = []
    ref_keys: set[tuple[str, str]] = set()
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict):
            errors.append(f"artifact_refs[{index}] must be an object")
            continue
        errors.extend(
            f"artifact_refs[{index}]: {msg}"
            for msg in validate_benchmark_artifact_ref_semantics(ref)
        )
        artifact_type = str(ref.get("artifact_type", ""))
        sha256 = ref.get("sha256")
        path = ref.get("path")
        if isinstance(path, str):
            paths.append(path)
        embedded = _embedded_ingest_objects(data, artifact_type)
        if not embedded:
            errors.append(
                f"artifact_refs[{index}]: no embedded objects for {artifact_type!r}",
            )
            continue
        if isinstance(sha256, str) and not any(
            row.get("signature_or_digest") == sha256 for row in embedded
        ):
            errors.append(
                f"artifact_refs[{index}]: sha256 does not match any embedded "
                f"{artifact_type} signature_or_digest",
            )
        elif isinstance(sha256, str):
            ref_keys.add((artifact_type, sha256))
    if len(paths) != len(set(paths)):
        errors.append("PcsBenchIngest.v0 artifact_refs contains duplicate path values")
    if has_producer_embedded:
        for field in producer_fields:
            rows = data.get(field)
            if not isinstance(rows, list):
                continue
            artifact_type = next(
                (atype for atype, fname in INGEST_EMBEDDED_ARRAYS.items() if fname == field),
                None,
            )
            if artifact_type is None:
                continue
            for row_index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                digest = row.get("signature_or_digest")
                if isinstance(digest, str) and (artifact_type, digest) not in ref_keys:
                    errors.append(
                        f"{field}[{row_index}]: missing artifact_refs entry for "
                        f"{artifact_type} digest {digest}",
                    )
    return errors


def validate_benchmark_suite_manifest_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    case_ids = data.get("case_ids")
    cases = data.get("cases")
    case_count = data.get("case_count")
    if not isinstance(case_ids, list):
        return ["BenchmarkSuiteManifest.v0 case_ids must be an array"]
    if not isinstance(cases, list):
        return ["BenchmarkSuiteManifest.v0 cases must be an array"]
    if isinstance(case_count, int) and case_count != len(case_ids):
        errors.append(
            f"case_count {case_count} does not match len(case_ids)={len(case_ids)}",
        )
    if isinstance(case_count, int) and case_count != len(cases):
        errors.append(
            f"case_count {case_count} does not match len(cases)={len(cases)}",
        )
    manifest_ids = [str(entry.get("case_id", "")) for entry in cases if isinstance(entry, dict)]
    if sorted(manifest_ids) != sorted(str(item) for item in case_ids):
        errors.append("case_ids must match cases[].case_id entries")
    if len(set(manifest_ids)) != len(manifest_ids):
        errors.append("duplicate case_id in cases[]")
    for index, entry in enumerate(cases):
        if not isinstance(entry, dict):
            errors.append(f"cases[{index}] must be an object")
            continue
        for key in ("case_id", "gallery_case_id", "path", "polarity"):
            if key not in entry:
                errors.append(f"cases[{index}] missing {key}")
    return errors


def validate_benchmark_registry_semantics(data: dict[str, Any]) -> list[str]:
    from pcs_core.benchmark_suite_manifest import load_benchmark_manifest, registry_matches_manifest
    from pcs_core.paths import repo_root

    errors: list[str] = []
    catalog = benchmark_suite_entries()
    suites = data.get("suites")
    if not isinstance(suites, dict):
        return ["BenchmarkRegistry.v0 suites must be an object"]
    if set(suites) != set(catalog):
        errors.append(
            f"suite keys drift from catalog (on_disk={sorted(suites)} catalog={sorted(catalog)})",
        )
    for suite_id, entry in suites.items():
        if not isinstance(entry, dict):
            continue
        fixture_root = repo_root() / str(entry.get("fixture_root", ""))
        manifest = load_benchmark_manifest(fixture_root)
        if manifest is not None:
            errors.extend(registry_matches_manifest(entry, manifest, suite_id=suite_id))
    return errors


def validate_benchmark_metric_registry_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    catalog = benchmark_metric_entries()
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        return ["BenchmarkMetricRegistry.v0 metrics must be an object"]
    if set(metrics) != set(catalog):
        errors.append(
            f"metric keys drift from catalog (on_disk={sorted(metrics)} catalog={sorted(catalog)})",
        )
    required_ids = {
        "release_reproducibility_score",
        "failure_localization_accuracy",
        "certificate_completeness_score",
        "registry_coverage_score",
        "formal_check_coverage_score",
        "scientific_memory_interpretability_score",
        "repair_hint_quality_score",
        "cross_domain_portability_score",
    }
    if not required_ids <= set(metrics):
        errors.append(f"missing metric ids: {sorted(required_ids - set(metrics))}")
    return errors
