"""Normalize repo-specific benchmark dialects to pcs-core v0 schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.benchmark_runner import build_failure_localization_result
from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.paths import examples_dir, repo_root
from pcs_core.protocol_fixtures import PCS_CORE_REPO
from pcs_core.release_canonical import LABTRUST_RC_PCS_CORE_COMMIT
from pcs_core.validate import ValidationError, validate_artifact, validate_file

PCS_COMMIT = LABTRUST_RC_PCS_CORE_COMMIT

EXPLAIN_QUALITY_SECTIONS: tuple[str, ...] = (
    "provenance",
    "hashes",
    "handoffs",
    "verification",
    "formal_checks",
    "limitations",
    "lineage",
    "repair_hints",
)


def _with_digest(doc: dict[str, Any]) -> dict[str, Any]:
    body = dict(doc)
    body["signature_or_digest"] = canonical_hash(
        {k: v for k, v in body.items() if k != "signature_or_digest"},
    )
    return body


def benchmarks_examples_dir() -> Path:
    return examples_dir() / "benchmarks"


def compatibility_dir() -> Path:
    return benchmarks_examples_dir() / "compatibility"


def normalize_pcs_bench_report(raw: dict[str, Any]) -> dict[str, Any]:
    """Map pcs-bench BenchmarkReport dialect to canonical BenchmarkReport.v0."""
    summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    body: dict[str, Any] = {
        "schema_version": "v0",
        "report_id": str(raw.get("report_id", "pcs-bench-report")),
        "benchmark_suite_id": str(
            raw.get("benchmark_suite_id", raw.get("suite_id", "unknown-suite")),
        ),
        "runs": raw.get("runs", []) if isinstance(raw.get("runs"), list) else [],
        "metrics": raw.get("metrics", ["release_reproducibility"])
        if isinstance(raw.get("metrics"), list)
        else ["release_reproducibility"],
        "summary": {
            "total_cases": int(summary.get("total_cases", 0)),
            "passed_cases": int(summary.get("passed_cases", 0)),
            "failed_cases": int(summary.get("failed_cases", 0)),
            "expected_failures_detected": int(summary.get("expected_failures_detected", 0)),
            "unexpected_passes": int(summary.get("unexpected_passes", 0)),
            "unexpected_failures": int(summary.get("unexpected_failures", 0)),
            "failure_localization_accuracy": float(
                summary.get("failure_localization_accuracy", 0.0),
            ),
            "repair_hint_accuracy": float(summary.get("repair_hint_accuracy", 0.0)),
            "formal_check_coverage": float(summary.get("formal_check_coverage", 0.0)),
            "registry_coverage": float(summary.get("registry_coverage", 0.0)),
            "scientific_memory_render_coverage": float(
                summary.get("scientific_memory_render_coverage", 0.0),
            ),
        },
        "coverage": raw.get("coverage", {}) if isinstance(raw.get("coverage"), dict) else {},
        "failures": raw.get("failures", []) if isinstance(raw.get("failures"), list) else [],
        "producer_id": "pcs-bench",
        "source_repo": str(raw.get("source_repo", PCS_CORE_REPO)),
        "source_commit": str(raw.get("source_commit", PCS_COMMIT)),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    if raw.get("conformance_refs"):
        body["conformance_refs"] = raw["conformance_refs"]
    return _with_digest(body)


def normalize_pf_explain_quality(raw: dict[str, Any]) -> dict[str, Any]:
    """Map Provability Fabric admission explain-quality output."""
    required = list(raw.get("required_sections", EXPLAIN_QUALITY_SECTIONS))
    section_scores = raw.get("sections") or raw.get("section_scores") or {}
    sections: dict[str, Any] = {}
    gaps: list[dict[str, str]] = []
    for section_id in required:
        entry = section_scores.get(section_id, {})
        if isinstance(entry, dict):
            present = bool(entry.get("present", entry.get("score", 0) >= 1.0))
            score = float(entry.get("score", 1.0 if present else 0.0))
        else:
            present = bool(entry)
            score = 1.0 if present else 0.0
        sections[section_id] = {"present": present, "score": min(1.0, max(0.0, score))}
        if not present:
            gaps.append(
                {
                    "section_id": section_id,
                    "message": f"PF admission benchmark missing section {section_id}",
                },
            )
    present_count = sum(1 for item in sections.values() if item.get("present"))
    required_count = len(required)
    quality = present_count / required_count if required_count else 0.0
    body: dict[str, Any] = {
        "schema_version": "v0",
        "report_id": str(raw.get("report_id", "pf-explain-quality-admission-v0")),
        "suite_id": str(raw.get("suite_id", "pf-admission-v0")),
        "case_id": str(raw.get("case_id", "admission-default")),
        "producer_id": "provability-fabric",
        "workflow_id": str(raw.get("workflow_id", "provability_fabric.admission_v0")),
        "required_sections": required,
        "sections": sections,
        "sections_present_count": present_count,
        "sections_required_count": required_count,
        "quality_score": float(raw.get("quality_score", quality)),
        "gaps": gaps,
        "source_repo": str(raw.get("source_repo", "https://github.com/SentinelOps-CI/provability-fabric")),
        "source_commit": str(raw.get("source_commit", PCS_COMMIT)),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


def normalize_pf_profile_coverage(raw: dict[str, Any]) -> dict[str, Any]:
    """Map PF profile coverage structures to ProfileCoverageReport.v0."""
    required_artifacts = list(raw.get("artifact_types_required", raw.get("required_artifacts", [])))
    covered_artifacts = list(raw.get("artifact_types_covered", raw.get("covered_artifacts", [])))
    required_checks = list(raw.get("semantic_checks_required", raw.get("required_checks", [])))
    covered_checks = list(raw.get("semantic_checks_covered", raw.get("covered_checks", [])))
    required_handoffs = list(raw.get("handoff_steps_required", raw.get("required_handoffs", [])))
    covered_handoffs = list(raw.get("handoff_steps_covered", raw.get("covered_handoffs", [])))
    numerator = float(
        raw.get(
            "numerator",
            len(covered_artifacts) + len(covered_checks) + len(covered_handoffs),
        ),
    )
    denominator = float(
        raw.get(
            "denominator",
            max(
                len(required_artifacts) + len(required_checks) + len(required_handoffs),
                1,
            ),
        ),
    )
    ratio = min(1.0, max(0.0, numerator / denominator))
    body: dict[str, Any] = {
        "schema_version": "v0",
        "coverage_id": str(raw.get("coverage_id", "pf-profile-coverage-v0")),
        "workflow_profile_id": str(raw.get("workflow_profile_id", "provability_fabric.admission_v0")),
        "producer_id": "provability-fabric",
        "suite_id": str(raw.get("suite_id", "pf-admission-v0")),
        "artifact_types_required": required_artifacts,
        "artifact_types_covered": covered_artifacts,
        "semantic_checks_required": required_checks,
        "semantic_checks_covered": covered_checks,
        "handoff_steps_required": required_handoffs,
        "handoff_steps_covered": covered_handoffs,
        "numerator": numerator,
        "denominator": denominator,
        "coverage_ratio": float(raw.get("coverage_ratio", ratio)),
        "details": raw.get("details", {}),
        "source_repo": str(raw.get("source_repo", "https://github.com/SentinelOps-CI/provability-fabric")),
        "source_commit": str(raw.get("source_commit", PCS_COMMIT)),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


def normalize_certifyedge_certificate_benchmark(raw: dict[str, Any]) -> dict[str, Any]:
    """Map CertifyEdge certificate benchmark output to CoverageReport.v0."""
    passed = float(raw.get("checks_passed", raw.get("passed", 0)))
    total = float(raw.get("checks_total", raw.get("total", max(passed, 1))))
    body: dict[str, Any] = {
        "schema_version": "v0",
        "coverage_id": str(raw.get("coverage_id", "certifyedge-certificate-benchmark-v0")),
        "metric": "certificate_completeness",
        "metric_id": "certificate_completeness_score",
        "numerator": passed,
        "denominator": total,
        "coverage_ratio": min(1.0, passed / total) if total else 0.0,
        "details": {
            "producer_id": "certifyedge",
            "certificate_id": raw.get("certificate_id"),
            "violations": raw.get("violations", []),
        },
        "source_repo": str(raw.get("source_repo", "https://github.com/fraware/CertifyEdge")),
        "source_commit": str(raw.get("source_commit", PCS_COMMIT)),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


def normalize_labtrust_case_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    """Map LabTrust benchmark case manifests to BenchmarkCase.v0."""
    body: dict[str, Any] = {
        "schema_version": "v0",
        "case_id": str(raw.get("case_id", raw.get("id", "labtrust-case"))),
        "task_id": str(raw.get("task_id", "labtrust-qc-release-v0")),
        "workflow_id": str(raw.get("workflow_id", "labtrust.qc_release_v0.1")),
        "case_kind": str(raw.get("case_kind", "valid_release")),
        "input_artifacts": raw.get("input_artifacts")
        or {
            "release_directory": str(
                raw.get("release_directory", "examples/labtrust-release"),
            ),
        },
        "expected_status": str(raw.get("expected_status", "passed")),
        "expected_failure_code": str(raw.get("expected_failure_code", "")),
        "expected_responsible_component": str(
            raw.get("expected_responsible_component", "unknown"),
        ),
        "expected_repair_hint_kind": str(raw.get("expected_repair_hint_kind", "none")),
        "source_repo": str(raw.get("source_repo", "https://github.com/fraware/LabTrust-Gym")),
        "source_commit": str(raw.get("source_commit", PCS_COMMIT)),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


def normalize_scientific_memory_render_benchmark(raw: dict[str, Any]) -> dict[str, Any]:
    """Map Scientific Memory rendering benchmark output to ExplainQualityReport.v0."""
    required = list(raw.get("required_sections", EXPLAIN_QUALITY_SECTIONS))
    sm_report = raw.get("import_report") or raw
    sections: dict[str, Any] = {}
    gaps: list[dict[str, str]] = []
    key_to_section = {
        "source_repo": "provenance",
        "source_commit": "provenance",
        "release_manifest_hash": "hashes",
        "release_chain_validation_status": "verification",
        "validation_profile": "verification",
        "render_path": "lineage",
        "strict": "limitations",
        "allow_legacy": "limitations",
        "bundle_shape": "lineage",
        "source_bundle_path": "handoffs",
    }
    for section_id in required:
        present = any(key_to_section.get(k) == section_id and k in sm_report for k in key_to_section)
        if section_id == "formal_checks":
            present = "release_chain_validation_status" in sm_report
        if section_id == "repair_hints":
            present = bool(raw.get("repair_hints")) or sm_report.get("verification_status") == "passed"
        sections[section_id] = {"present": present, "score": 1.0 if present else 0.0}
        if not present:
            gaps.append(
                {
                    "section_id": section_id,
                    "message": f"Scientific Memory render benchmark missing {section_id}",
                },
            )
    present_count = sum(1 for item in sections.values() if item.get("present"))
    required_count = len(required)
    body: dict[str, Any] = {
        "schema_version": "v0",
        "report_id": str(raw.get("report_id", "sm-render-benchmark-v0")),
        "suite_id": str(raw.get("suite_id", "scientific-memory-rendering-v0")),
        "case_id": str(raw.get("case_id", "valid-scientific-memory-import")),
        "producer_id": "scientific-memory",
        "workflow_id": str(raw.get("workflow_id", "labtrust.qc_release_v0.1")),
        "required_sections": required,
        "sections": sections,
        "sections_present_count": present_count,
        "sections_required_count": required_count,
        "quality_score": present_count / required_count if required_count else 0.0,
        "gaps": gaps,
        "source_repo": str(raw.get("source_repo", "https://github.com/fraware/scientific-memory")),
        "source_commit": str(raw.get("source_commit", PCS_COMMIT)),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


DIALECT_FILE_NAMES: tuple[str, ...] = (
    "pcs_bench_report.dialect.json",
    "pf_admission_explain_quality.dialect.json",
    "pf_profile_coverage.dialect.json",
    "certifyedge_certificate_benchmark.dialect.json",
    "labtrust_case_manifest.dialect.json",
    "scientific_memory_render_benchmark.dialect.json",
)

NORMALIZERS: dict[str, tuple[str, Any]] = {
    "pcs_bench_report.dialect.json": ("BenchmarkReport.v0", normalize_pcs_bench_report),
    "pf_admission_explain_quality.dialect.json": ("ExplainQualityReport.v0", normalize_pf_explain_quality),
    "pf_profile_coverage.dialect.json": ("ProfileCoverageReport.v0", normalize_pf_profile_coverage),
    "certifyedge_certificate_benchmark.dialect.json": (
        "CoverageReport.v0",
        normalize_certifyedge_certificate_benchmark,
    ),
    "labtrust_case_manifest.dialect.json": ("BenchmarkCase.v0", normalize_labtrust_case_manifest),
    "scientific_memory_render_benchmark.dialect.json": (
        "ExplainQualityReport.v0",
        normalize_scientific_memory_render_benchmark,
    ),
}


def validate_compatibility_corpus() -> list[str]:
    """Validate canonical examples and normalize dialect fixtures."""
    errors: list[str] = []
    examples_root = benchmarks_examples_dir()
    for name in (
        "benchmark_case.valid.json",
        "benchmark_run.valid.json",
        "benchmark_report.valid.json",
        "failure_localization_result.valid.json",
        "coverage_report.valid.json",
        "explain_quality_report.valid.json",
        "profile_coverage_report.valid.json",
    ):
        path = examples_root / name
        if not path.is_file():
            errors.append(f"missing {path.relative_to(repo_root()).as_posix()}")
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"{name}: {exc}")

    metric_registry = examples_dir() / "benchmark_metric_registry.valid.json"
    if not metric_registry.is_file():
        errors.append("missing examples/benchmark_metric_registry.valid.json")
    else:
        try:
            validate_file(metric_registry)
        except ValidationError as exc:
            errors.append(f"benchmark_metric_registry.valid.json: {exc}")

    compat = compatibility_dir()
    for dialect_name, (artifact_type, normalizer) in NORMALIZERS.items():
        dialect_path = compat / dialect_name
        if not dialect_path.is_file():
            errors.append(f"missing compatibility dialect {dialect_name}")
            continue
        try:
            raw = json.loads(dialect_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                errors.append(f"{dialect_name}: root must be object")
                continue
            normalized = normalizer(raw)
            validate_artifact(normalized, artifact_type)
            out_name = dialect_name.replace(".dialect.json", ".normalized.json")
            out_path = compat / out_name
            if out_path.is_file():
                on_disk = json.loads(out_path.read_text(encoding="utf-8"))
                validate_artifact(on_disk, artifact_type)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{dialect_name}: {exc}")
    return errors


def build_failure_localization_example() -> dict[str, Any]:
    from pcs_core.benchmark_runner import execute_benchmark_case, load_benchmark_case

    case_path = (
        repo_root()
        / "benchmarks/labtrust-qc-release/invalid/invalid-certificate-id/benchmark_case.v0.json"
    )
    case = load_benchmark_case(case_path)
    run = execute_benchmark_case(case)
    return build_failure_localization_result(case, run)
