#!/usr/bin/env python3
"""Materialize examples/benchmarks/*.valid.json and compatibility dialect fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from pcs_core.benchmark_compat import (  # noqa: E402
    EXPLAIN_QUALITY_SECTIONS,
    INGEST_NORMALIZERS,
    compatibility_dir,
    normalize_certifyedge_certificate_benchmark,
    normalize_labtrust_case_manifest,
    normalize_pf_explain_quality,
    normalize_pf_profile_coverage,
    normalize_pcs_bench_report,
    normalize_scientific_memory_render_benchmark,
)
from pcs_core.benchmark_metric_registry import build_benchmark_metric_registry  # noqa: E402
from pcs_core.benchmark_runner import (  # noqa: E402
    build_failure_localization_result,
    execute_benchmark_case,
    load_benchmark_case,
)
from pcs_core.hash import canonical_hash  # noqa: E402
from pcs_core.paths import examples_dir, repo_root  # noqa: E402
from pcs_core.protocol_fixtures import PCS_CORE_REPO  # noqa: E402
from pcs_core.release_canonical import LABTRUST_RC_PCS_CORE_COMMIT  # noqa: E402
from pcs_core.validate import validate_file  # noqa: E402

PCS_COMMIT = LABTRUST_RC_PCS_CORE_COMMIT
EXAMPLES = examples_dir() / "benchmarks"


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _scrub_run_paths(run: dict[str, Any]) -> dict[str, Any]:
    body = dict(run)
    for command in body.get("commands", []):
        if isinstance(command, dict) and "command" in command:
            cmd = str(command["command"])
            if "validate_release_chain" in cmd:
                command["command"] = "validate_release_chain examples/labtrust-release"
    return body


def main() -> int:
    compat = compatibility_dir()
    case_src = (
        repo_root()
        / "benchmarks/labtrust-qc-release/valid/labtrust-valid-release-v0/benchmark_case.v0.json"
    )
    canonical_case = load_benchmark_case(case_src)
    run = execute_benchmark_case(canonical_case)
    _write_json(EXAMPLES / "benchmark_case.valid.json", canonical_case)
    _write_json(EXAMPLES / "benchmark_run.valid.json", _scrub_run_paths(run))

    _write_json(
        EXAMPLES / "labtrust_benchmark_case.valid.json",
        canonical_case,
    )

    for dialect_name, (_artifact_type, normalizer) in INGEST_NORMALIZERS.items():
        dialect_path = compat / dialect_name
        if not dialect_path.is_file():
            continue
        raw = json.loads(dialect_path.read_text(encoding="utf-8"))
        ingest = normalizer(raw)
        out_name = dialect_name.replace(
            ".dialect.json",
            ".pcs_bench_ingest.normalized.json",
        )
        _write_json(compat / out_name, ingest)

    report_src = (
        repo_root()
        / "benchmarks/labtrust-qc-release/expected_reports/benchmark_report.v0.json"
    )
    report = json.loads(report_src.read_text(encoding="utf-8"))
    report["producer_id"] = "pcs-core"
    _write_json(EXAMPLES / "benchmark_report.valid.json", report)

    summaries = report.get("metric_summaries")
    if isinstance(summaries, list) and summaries:
        _write_json(EXAMPLES / "metric_summary.valid.json", summaries[0])

    invalid_case = load_benchmark_case(
        repo_root()
        / "benchmarks/labtrust-qc-release/invalid/labtrust-certificate-id-tamper-v0/benchmark_case.v0.json",
    )
    invalid_run = execute_benchmark_case(invalid_case)
    _write_json(
        EXAMPLES / "failure_localization_result.valid.json",
        build_failure_localization_result(invalid_case, invalid_run),
    )

    if "coverage" in report and isinstance(report["coverage"], dict):
        registry_cov = report["coverage"].get("registry")
        if isinstance(registry_cov, dict):
            _write_json(EXAMPLES / "coverage_report.valid.json", registry_cov)

    sm_path = repo_root() / "examples/labtrust-release/scientific_memory_import_report.json"
    explain = normalize_scientific_memory_render_benchmark(
        {
            "import_report": json.loads(sm_path.read_text(encoding="utf-8")),
            "suite_id": "scientific-memory-rendering-v0",
            "case_id": "valid-scientific-memory-import",
        },
    )
    _write_json(EXAMPLES / "explain_quality_report.valid.json", explain)

    profile = normalize_pf_profile_coverage(
        {
            "workflow_profile_id": "labtrust.qc_release_v0.1",
            "artifact_types_required": [
                "RuntimeReceipt.v0",
                "TraceCertificate.v0",
                "ScienceClaimBundle.v0",
                "VerificationResult.v0",
                "SignedScienceClaimBundle.v0",
            ],
            "artifact_types_covered": [
                "RuntimeReceipt.v0",
                "TraceCertificate.v0",
                "ScienceClaimBundle.v0",
                "VerificationResult.v0",
                "SignedScienceClaimBundle.v0",
            ],
            "semantic_checks_required": ["trace_hash_matches_certificate"],
            "semantic_checks_covered": ["trace_hash_matches_certificate"],
            "handoff_steps_required": ["runtime_to_certificate"],
            "handoff_steps_covered": ["runtime_to_certificate"],
            "suite_id": "labtrust-qc-release-v0",
        },
    )
    _write_json(EXAMPLES / "profile_coverage_report.valid.json", profile)

    _write_json(
        compat / "pcs_bench_report.dialect.json",
        {
            "schema_version": "v0",
            "report_id": "pcs-bench-report-labtrust-v0",
            "suite_id": "labtrust-qc-release-v0",
            "benchmark_suite_id": "labtrust-qc-release-v0",
            "runs": report.get("runs", [])[:2],
            "metrics": report.get("metrics", []),
            "summary": report.get("summary", {}),
            "coverage": report.get("coverage", {}),
            "failures": [],
            "source_repo": PCS_CORE_REPO,
            "source_commit": PCS_COMMIT,
            "signature_or_digest": "sha256:" + "0" * 64,
        },
    )
    _write_json(
        compat / "pcs_bench_report.normalized.json",
        normalize_pcs_bench_report(
            json.loads((compat / "pcs_bench_report.dialect.json").read_text(encoding="utf-8")),
        ),
    )

    _write_json(
        compat / "pf_admission_explain_quality.dialect.json",
        {
            "report_id": "pf-admission-explain-v0",
            "suite_id": "pf-admission-v0",
            "case_id": "bundle-admission",
            "required_sections": list(EXPLAIN_QUALITY_SECTIONS),
            "section_scores": {section: {"present": True, "score": 1.0} for section in EXPLAIN_QUALITY_SECTIONS},
            "quality_score": 1.0,
        },
    )
    _write_json(
        compat / "pf_admission_explain_quality.normalized.json",
        normalize_pf_explain_quality(
            json.loads(
                (compat / "pf_admission_explain_quality.dialect.json").read_text(encoding="utf-8"),
            ),
        ),
    )

    _write_json(
        compat / "pf_profile_coverage.dialect.json",
        {
            "workflow_profile_id": "provability_fabric.admission_v0",
            "required_artifacts": ["VerificationResult.v0", "SignedScienceClaimBundle.v0"],
            "covered_artifacts": ["VerificationResult.v0", "SignedScienceClaimBundle.v0"],
            "required_checks": ["signed_input_hash_matches_verified_input"],
            "covered_checks": ["signed_input_hash_matches_verified_input"],
            "required_handoffs": ["bundle_to_verifier"],
            "covered_handoffs": ["bundle_to_verifier"],
        },
    )
    _write_json(
        compat / "pf_profile_coverage.normalized.json",
        normalize_pf_profile_coverage(
            json.loads((compat / "pf_profile_coverage.dialect.json").read_text(encoding="utf-8")),
        ),
    )

    _write_json(
        compat / "certifyedge_certificate_benchmark.dialect.json",
        {
            "coverage_id": "certifyedge-cert-bench-v0",
            "certificate_id": "cert-labtrust-qc-v0",
            "checks_passed": 4,
            "checks_total": 4,
            "violations": [],
        },
    )
    _write_json(
        compat / "certifyedge_certificate_benchmark.normalized.json",
        normalize_certifyedge_certificate_benchmark(
            json.loads(
                (compat / "certifyedge_certificate_benchmark.dialect.json").read_text(
                    encoding="utf-8",
                ),
            ),
        ),
    )

    _write_json(
        compat / "labtrust_case_manifest.dialect.json",
        {
            "case_id": "labtrust-qc-valid-release",
            "workflow_id": "labtrust.qc_release_v0.1",
            "release_directory": "examples/labtrust-release",
            "expected_status": "passed",
        },
    )
    _write_json(
        compat / "labtrust_case_manifest.normalized.json",
        normalize_labtrust_case_manifest(
            json.loads((compat / "labtrust_case_manifest.dialect.json").read_text(encoding="utf-8")),
        ),
    )

    _write_json(
        compat / "scientific_memory_render_benchmark.dialect.json",
        {
            "import_report": json.loads(sm_path.read_text(encoding="utf-8")),
            "suite_id": "scientific-memory-rendering-v0",
        },
    )
    _write_json(
        compat / "scientific_memory_render_benchmark.normalized.json",
        normalize_scientific_memory_render_benchmark(
            json.loads(
                (compat / "scientific_memory_render_benchmark.dialect.json").read_text(
                    encoding="utf-8",
                ),
            ),
        ),
    )

    metric_registry_path = examples_dir() / "benchmark_metric_registry.valid.json"
    _write_json(metric_registry_path, build_benchmark_metric_registry())
    validate_file(metric_registry_path)

    for rel in (
        "examples/benchmarks/benchmark_case.valid.json",
        "examples/benchmarks/benchmark_report.valid.json",
        "examples/benchmarks/metric_summary.valid.json",
        "examples/benchmarks/explain_quality_report.valid.json",
        "examples/benchmarks/profile_coverage_report.valid.json",
        "examples/benchmarks/compatibility/pcs_bench_report.normalized.json",
    ):
        validate_file(repo_root() / rel)

    print("Wrote examples/benchmarks and benchmark_metric_registry.valid.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
