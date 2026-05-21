"""Normalize repo-specific benchmark dialects to pcs-core v0 schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.benchmark_metrics import (
    _metric_summary,
    build_metric_summaries_from_report,
    coerce_metric_ids,
)
from pcs_core.benchmark_runner import build_failure_localization_result
from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.paths import examples_dir, repo_root
from pcs_core.protocol_fixtures import PCS_CORE_REPO
from pcs_core.release_canonical import LABTRUST_RC_PCS_CORE_COMMIT
from pcs_core.validate import ValidationError, validate_artifact, validate_file

PCS_COMMIT = LABTRUST_RC_PCS_CORE_COMMIT

INGEST_EMBEDDED_ARRAYS: dict[str, str] = {
    "BenchmarkRun.v0": "benchmark_runs",
    "CoverageReport.v0": "coverage_reports",
    "FailureLocalizationResult.v0": "failure_localization_reports",
    "ExplainQualityReport.v0": "explain_quality_reports",
    "ProfileCoverageReport.v0": "profile_coverage_reports",
}

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


def _coerce_metric_summaries_list(rows: list[Any]) -> list[dict[str, Any]]:
    """Normalize legacy metric summary rows (name -> metric_id) to MetricSummary.v0."""
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_id = row.get("metric_id") or row.get("name")
        if not isinstance(raw_id, str):
            continue
        metric_id = coerce_metric_ids([raw_id])[0]
        if row.get("schema_version") == "v0" and isinstance(row.get("signature_or_digest"), str):
            body = dict(row)
            body["metric_id"] = metric_id
            out.append(body)
            continue
        score = row.get("score")
        out.append(
            _metric_summary(
                metric_id=metric_id,
                score=float(score if score is not None else 0.0),
                applicability=str(row.get("applicability", "measured")),
                numerator=float(row.get("numerator", 0)),
                denominator=float(row.get("denominator", 0)),
                reason=str(row.get("reason", "")),
                details=row.get("details") if isinstance(row.get("details"), dict) else {},
            ),
        )
    return out


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
        "metrics": coerce_metric_ids(
            raw.get("metrics", ["release_reproducibility_score"])
            if isinstance(raw.get("metrics"), list)
            else ["release_reproducibility_score"],
        ),
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
    if isinstance(raw.get("metric_summaries"), list):
        body["metric_summaries"] = _coerce_metric_summaries_list(raw["metric_summaries"])
    else:
        body["metric_summaries"] = build_metric_summaries_from_report(body)
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


_DETECTION_LAYER_ALIASES: dict[str, str] = {
    "LabTrust": "labtrust",
    "CertifyEdge": "certifyedge",
    "Provability Fabric": "provability_fabric",
    "Scientific Memory": "scientific_memory",
    "Lean trust kernel": "formal_kernel",
    "runtime_producer": "runtime",
    "certificate_producer": "certificate",
}


def _coerce_detection_layer(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return _DETECTION_LAYER_ALIASES.get(text, text.lower().replace(" ", "_"))


def build_benchmark_artifact_ref(
    *,
    artifact_type: str,
    path: str,
    embedded: dict[str, Any],
    role: str = "producer_export",
    source_repo: str,
    source_commit: str = PCS_COMMIT,
) -> dict[str, Any]:
    """Build BenchmarkArtifactRef.v0 for on-disk provenance of an embedded object."""
    content_digest = embedded.get("signature_or_digest", PLACEHOLDER_DIGEST)
    body: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": artifact_type,
        "path": path,
        "sha256": content_digest,
        "role": role,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


def build_pcs_bench_ingest(
    *,
    producer_id: str,
    suite_id: str,
    workflow_id: str,
    benchmark_runs: list[dict[str, Any]] | None = None,
    coverage_reports: list[dict[str, Any]] | None = None,
    failure_localization_reports: list[dict[str, Any]] | None = None,
    explain_quality_reports: list[dict[str, Any]] | None = None,
    profile_coverage_reports: list[dict[str, Any]] | None = None,
    artifact_refs: list[dict[str, Any]] | None = None,
    commands: list[dict[str, Any]] | None = None,
    logs: list[str] | None = None,
    source_repo: str,
    source_commit: str = PCS_COMMIT,
) -> dict[str, Any]:
    """Assemble PcsBenchIngest.v0 from normalized sub-artifacts."""
    body: dict[str, Any] = {
        "schema_version": "v0",
        "producer_id": producer_id,
        "suite_id": suite_id,
        "workflow_id": workflow_id,
        "benchmark_runs": list(benchmark_runs or []),
        "coverage_reports": list(coverage_reports or []),
        "failure_localization_reports": list(failure_localization_reports or []),
        "explain_quality_reports": list(explain_quality_reports or []),
        "profile_coverage_reports": list(profile_coverage_reports or []),
        "commands": list(commands or []),
        "logs": list(logs or []),
        "source_repo": source_repo,
        "source_commit": source_commit,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    if artifact_refs:
        body["artifact_refs"] = list(artifact_refs)
    return _with_digest(body)


def build_certifyedge_pcs_bench_ingest(raw: dict[str, Any]) -> dict[str, Any]:
    coverage = normalize_certifyedge_certificate_benchmark(raw)
    source_repo = str(raw.get("source_repo", "https://github.com/fraware/CertifyEdge"))
    source_commit = str(raw.get("source_commit", PCS_COMMIT))
    coverage_path = str(
        raw.get(
            "coverage_report_path",
            "benchmarks/certificate/coverage_report.certifyedge-cert-bench-v0.v0.json",
        ),
    )
    commands = raw.get("commands")
    if not isinstance(commands, list):
        commands = [
            {
                "command": f"certifyedge_certificate_benchmark {raw.get('certificate_id', 'unknown')}",
                "exit_code": 0 if float(raw.get("checks_passed", 0)) >= float(raw.get("checks_total", 1)) else 1,
            },
        ]
    return build_pcs_bench_ingest(
        producer_id="certifyedge",
        suite_id=str(raw.get("suite_id", "certifyedge-certificate-v0")),
        workflow_id=str(raw.get("workflow_id", "labtrust.qc_release_v0.1")),
        coverage_reports=[coverage],
        artifact_refs=[
            build_benchmark_artifact_ref(
                artifact_type="CoverageReport.v0",
                path=coverage_path,
                embedded=coverage,
                source_repo=source_repo,
                source_commit=source_commit,
            ),
        ],
        commands=commands,
        logs=[str(line) for line in raw.get("logs", [])] if isinstance(raw.get("logs"), list) else [],
        source_repo=source_repo,
        source_commit=source_commit,
    )


def build_pf_pcs_bench_ingest(
    explain_raw: dict[str, Any],
    profile_raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    explain = normalize_pf_explain_quality(explain_raw)
    source_repo = str(
        explain_raw.get("source_repo", "https://github.com/SentinelOps-CI/provability-fabric"),
    )
    source_commit = str(explain_raw.get("source_commit", PCS_COMMIT))
    profiles: list[dict[str, Any]] = []
    artifact_refs: list[dict[str, Any]] = [
        build_benchmark_artifact_ref(
            artifact_type="ExplainQualityReport.v0",
            path=str(
                explain_raw.get(
                    "explain_quality_report_path",
                    "benchmarks/admission/explain_quality_report.pf-explain-quality-admission-v0.v0.json",
                ),
            ),
            embedded=explain,
            source_repo=source_repo,
            source_commit=source_commit,
        ),
    ]
    if isinstance(profile_raw, dict):
        profile = normalize_pf_profile_coverage(profile_raw)
        profiles.append(profile)
        artifact_refs.append(
            build_benchmark_artifact_ref(
                artifact_type="ProfileCoverageReport.v0",
                path=str(
                    profile_raw.get(
                        "profile_coverage_report_path",
                        "benchmarks/admission/profile_coverage_report.pf-profile-coverage-v0.v0.json",
                    ),
                ),
                embedded=profile,
                source_repo=source_repo,
                source_commit=source_commit,
            ),
        )
    commands = explain_raw.get("commands")
    if not isinstance(commands, list):
        commands = [
            {
                "command": "provability_fabric_admission_explain_quality",
                "exit_code": 0 if float(explain.get("quality_score", 0)) >= 1.0 else 1,
            },
        ]
    return build_pcs_bench_ingest(
        producer_id="provability-fabric",
        suite_id=str(explain_raw.get("suite_id", "pf-admission-v0")),
        workflow_id=str(explain_raw.get("workflow_id", "provability_fabric.admission_v0")),
        explain_quality_reports=[explain],
        profile_coverage_reports=profiles,
        artifact_refs=artifact_refs,
        commands=commands,
        logs=[str(line) for line in explain_raw.get("logs", [])] if isinstance(explain_raw.get("logs"), list) else [],
        source_repo=source_repo,
        source_commit=source_commit,
    )


def build_scientific_memory_pcs_bench_ingest(raw: dict[str, Any]) -> dict[str, Any]:
    explain = normalize_scientific_memory_render_benchmark(raw)
    sm_report = raw.get("import_report") or raw
    source_repo = str(raw.get("source_repo", sm_report.get("source_repo", "https://github.com/fraware/scientific-memory")))
    source_commit = str(
        raw.get("source_commit", sm_report.get("scientific_memory_commit", PCS_COMMIT)),
    )
    explain_path = str(
        raw.get(
            "explain_quality_report_path",
            "benchmarks/rendering/explain_quality_report.sm-render-benchmark-v0.v0.json",
        ),
    )
    commands = raw.get("commands")
    if not isinstance(commands, list):
        commands = [
            {
                "command": "scientific_memory_render_benchmark",
                "exit_code": 0 if float(explain.get("quality_score", 0)) >= 1.0 else 1,
            },
        ]
    return build_pcs_bench_ingest(
        producer_id="scientific-memory",
        suite_id=str(raw.get("suite_id", "scientific-memory-rendering-v0")),
        workflow_id=str(raw.get("workflow_id", "labtrust.qc_release_v0.1")),
        explain_quality_reports=[explain],
        artifact_refs=[
            build_benchmark_artifact_ref(
                artifact_type="ExplainQualityReport.v0",
                path=explain_path,
                embedded=explain,
                source_repo=source_repo,
                source_commit=source_commit,
            ),
        ],
        commands=commands,
        logs=[str(line) for line in raw.get("logs", [])] if isinstance(raw.get("logs"), list) else [],
        source_repo=source_repo,
        source_commit=source_commit,
    )


def build_labtrust_pcs_bench_ingest(
    *,
    case: dict[str, Any],
    run: dict[str, Any],
    run_path: str,
    source_repo: str | None = None,
    source_commit: str | None = None,
) -> dict[str, Any]:
    """Assemble LabTrust-Gym PcsBenchIngest.v0 with embedded run and file provenance ref."""
    repo = source_repo or str(case.get("source_repo", "https://github.com/fraware/LabTrust-Gym"))
    commit = source_commit or str(case.get("source_commit", PCS_COMMIT))
    return build_pcs_bench_ingest(
        producer_id="labtrust-gym",
        suite_id=str(case.get("task_id", "labtrust-qc-release-v0")),
        workflow_id=str(case.get("workflow_id", "labtrust.qc_release_v0.1")),
        benchmark_runs=[run],
        artifact_refs=[
            build_benchmark_artifact_ref(
                artifact_type="BenchmarkRun.v0",
                path=run_path,
                embedded=run,
                source_repo=repo,
                source_commit=commit,
            ),
        ],
        commands=[
            {
                "command": f"labtrust_benchmark_case {case.get('case_id', 'unknown')}",
                "exit_code": 0 if run.get("observed_status") == "passed" else 1,
            },
        ],
        logs=[],
        source_repo=repo,
        source_commit=commit,
    )


def normalize_labtrust_case_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    """Map LabTrust benchmark case manifests to BenchmarkCase.v0."""
    case_kind = str(raw.get("case_kind", "valid_release"))
    if case_kind == "valid_release":
        expected_failure_code = None
        expected_responsible_component = None
        expected_repair_hint_kind = None
    else:
        expected_failure_code = raw.get("expected_failure_code")
        expected_responsible_component = raw.get("expected_responsible_component", "unknown")
        expected_repair_hint_kind = raw.get("expected_repair_hint_kind", "unknown")
    body: dict[str, Any] = {
        "schema_version": "v0",
        "case_id": str(raw.get("case_id", raw.get("id", "labtrust-case"))),
        "task_id": str(raw.get("task_id", "labtrust-qc-release-v0")),
        "workflow_id": str(raw.get("workflow_id", "labtrust.qc_release_v0.1")),
        "case_kind": case_kind,
        "input_artifacts": raw.get("input_artifacts")
        or {
            "release_directory": str(
                raw.get("release_directory", "examples/labtrust-release"),
            ),
        },
        "expected_status": str(raw.get("expected_status", "passed")),
        "expected_failure_code": expected_failure_code,
        "expected_responsible_component": expected_responsible_component,
        "expected_repair_hint_kind": expected_repair_hint_kind,
        "source_repo": str(raw.get("source_repo", "https://github.com/fraware/LabTrust-Gym")),
        "source_commit": str(raw.get("source_commit", PCS_COMMIT)),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    layer = _coerce_detection_layer(
        raw.get("expected_detection_layer", raw.get("detection_layer")),
    )
    if layer is not None:
        body["expected_detection_layer"] = layer
    outcome = raw.get("expected_system_outcome")
    if outcome is not None:
        body["expected_system_outcome"] = outcome
    elif case_kind == "valid_release":
        body["expected_system_outcome"] = "admitted"
    else:
        body["expected_system_outcome"] = "rejected"
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

def normalize_pf_pcs_bench_ingest_dialect(raw: dict[str, Any]) -> dict[str, Any]:
    profile_raw = None
    profile_path = compatibility_dir() / "pf_profile_coverage.dialect.json"
    if profile_path.is_file():
        profile_raw = json.loads(profile_path.read_text(encoding="utf-8"))
    return build_pf_pcs_bench_ingest(raw, profile_raw)


INGEST_NORMALIZERS: dict[str, tuple[str, Any]] = {
    "certifyedge_certificate_benchmark.dialect.json": (
        "PcsBenchIngest.v0",
        build_certifyedge_pcs_bench_ingest,
    ),
    "pf_admission_explain_quality.dialect.json": (
        "PcsBenchIngest.v0",
        normalize_pf_pcs_bench_ingest_dialect,
    ),
    "scientific_memory_render_benchmark.dialect.json": (
        "PcsBenchIngest.v0",
        build_scientific_memory_pcs_bench_ingest,
    ),
}

ALL_NORMALIZERS: dict[str, tuple[str, Any]] = {**NORMALIZERS, **INGEST_NORMALIZERS}


def validate_compatibility_corpus() -> list[str]:
    """Validate canonical examples and normalize dialect fixtures."""
    errors: list[str] = []
    examples_root = benchmarks_examples_dir()
    producer_root = examples_dir() / "benchmark"
    ingest_root = examples_dir() / "benchmark_ingest"
    for name in (
        "labtrust.pcs_bench_ingest.valid.json",
        "certifyedge.pcs_bench_ingest.valid.json",
        "provability_fabric.pcs_bench_ingest.valid.json",
        "scientific_memory.pcs_bench_ingest.valid.json",
    ):
        path = ingest_root / name
        if not path.is_file():
            errors.append(f"missing {path.relative_to(repo_root()).as_posix()}")
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"{name}: {exc}")

    for name in ("pcs_bench_report.valid.json", "labtrust_benchmark_case.valid.json"):
        path = producer_root / name
        if not path.is_file():
            errors.append(f"missing {path.relative_to(repo_root()).as_posix()}")
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"{name}: {exc}")

    for name in (
        "benchmark_case.valid.json",
        "benchmark_run.valid.json",
        "benchmark_report.valid.json",
        "benchmark_artifact_ref.valid.json",
        "failure_localization_result.valid.json",
        "coverage_report.valid.json",
        "explain_quality_report.valid.json",
        "profile_coverage_report.valid.json",
        "metric_summary.valid.json",
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
    for dialect_name, (artifact_type, normalizer) in ALL_NORMALIZERS.items():
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
            if dialect_name in INGEST_NORMALIZERS:
                out_name = dialect_name.replace(".dialect.json", ".pcs_bench_ingest.normalized.json")
            else:
                out_name = dialect_name.replace(".dialect.json", ".normalized.json")
            out_path = compat / out_name
            if out_path.is_file():
                on_disk = json.loads(out_path.read_text(encoding="utf-8"))
                validate_artifact(on_disk, artifact_type)
                if normalized != on_disk:
                    errors.append(
                        f"{dialect_name}: drift vs {out_name} "
                        "(run materialize_benchmark_examples.py or materialize_benchmark_producer_examples.py)",
                    )
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{dialect_name}: {exc}")
    return errors


def build_failure_localization_example() -> dict[str, Any]:
    from pcs_core.benchmark_runner import execute_benchmark_case, load_benchmark_case

    case_path = (
        repo_root()
        / "benchmarks/labtrust-qc-release/invalid/labtrust-certificate-id-tamper-v0/benchmark_case.v0.json"
    )
    case = load_benchmark_case(case_path)
    run = execute_benchmark_case(case)
    return build_failure_localization_result(case, run)
