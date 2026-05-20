#!/usr/bin/env python3
"""Materialize benchmarks/ fixtures and examples/benchmark_registry.valid.json."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from pcs_core.benchmark_registry import build_benchmark_registry  # noqa: E402
from pcs_core.registry import build_artifact_registry  # noqa: E402
from pcs_core.benchmark_runner import run_benchmark_suite  # noqa: E402
from pcs_core.hash import canonical_hash  # noqa: E402
from pcs_core.paths import examples_dir, repo_root  # noqa: E402
from pcs_core.protocol_fixtures import PCS_CORE_REPO  # noqa: E402
from pcs_core.release_canonical import LABTRUST_RC_PCS_CORE_COMMIT  # noqa: E402
from pcs_core.validate import validate_file  # noqa: E402

PCS_COMMIT = LABTRUST_RC_PCS_CORE_COMMIT

_SYSTEM_OUTCOME_BY_CASE_KIND: dict[str, str] = {
    "valid_release": "admitted",
    "invalid_certificate": "rejected",
    "invalid_hash_mismatch": "rejected",
    "invalid_handoff": "rejected",
    "invalid_registry": "rejected",
    "invalid_formal_check": "formal_failed",
    "invalid_import": "import_failed",
    "invalid_render": "render_failed",
    "stale_release": "stale",
}

_STANDARD_METRICS = [
    "release_reproducibility_score",
    "failure_localization_accuracy",
    "certificate_completeness_score",
    "registry_coverage_score",
    "formal_check_coverage_score",
    "scientific_memory_interpretability_score",
]


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _with_digest(doc: dict[str, Any]) -> dict[str, Any]:
    body = dict(doc)
    body["signature_or_digest"] = canonical_hash({k: v for k, v in body.items() if k != "signature_or_digest"})
    return body


def _benchmark_task(
    *,
    task_id: str,
    workflow_id: str,
    domain: str,
    fixture_root: str,
    case_count: int,
) -> dict[str, Any]:
    return _with_digest(
        {
            "schema_version": "v0",
            "task_id": task_id,
            "workflow_id": workflow_id,
            "domain": domain,
            "description": f"PCS benchmark task for {task_id}",
            "input_case_set": {"path": f"{fixture_root}", "case_count": case_count},
            "expected_outputs": {
                "report_artifact_type": "BenchmarkReport.v0",
                "minimum_pass_rate": 1.0,
            },
            "metrics": list(_STANDARD_METRICS),
            "success_criteria": {
                "minimum_pass_rate": 1.0,
                "minimum_failure_localization_accuracy": 1.0,
                "minimum_formal_check_coverage": 1.0,
                "minimum_registry_coverage": 0.95,
            },
            "source_repo": PCS_CORE_REPO,
            "source_commit": PCS_COMMIT,
            "signature_or_digest": "sha256:" + "0" * 64,
        },
    )


def _benchmark_case(
    *,
    case_id: str,
    task_id: str,
    workflow_id: str,
    case_kind: str,
    release_directory: str,
    expected_status: str,
    expected_system_outcome: str,
    expected_failure_code: str | None,
    expected_responsible_component: str | None,
    expected_repair_hint_kind: str | None,
) -> dict[str, Any]:
    return _with_digest(
        {
            "schema_version": "v0",
            "case_id": case_id,
            "task_id": task_id,
            "workflow_id": workflow_id,
            "case_kind": case_kind,
            "input_artifacts": {"release_directory": release_directory},
            "expected_status": expected_status,
            "expected_system_outcome": expected_system_outcome,
            "expected_failure_code": expected_failure_code,
            "expected_responsible_component": expected_responsible_component,
            "expected_repair_hint_kind": expected_repair_hint_kind,
            "source_repo": PCS_CORE_REPO,
            "source_commit": PCS_COMMIT,
            "signature_or_digest": "sha256:" + "0" * 64,
        },
    )


def _expected_failure(
    *,
    case_id: str,
    task_id: str,
    failure_code: str,
    responsible_component: str,
    repair_hint_kind: str,
    message: str,
) -> dict[str, Any]:
    return _with_digest(
        {
            "schema_version": "v0",
            "manifest_id": f"failure-manifest-{case_id}",
            "case_id": case_id,
            "task_id": task_id,
            "failure_code": failure_code,
            "responsible_component": responsible_component,
            "repair_hint_kind": repair_hint_kind,
            "message": message,
            "source_repo": PCS_CORE_REPO,
            "source_commit": PCS_COMMIT,
            "signature_or_digest": "sha256:" + "0" * 64,
        },
    )


def _expected_repair_hint(repair_hint_kind: str, message: str) -> dict[str, Any]:
    return {"repair_hint_kind": repair_hint_kind, "message": message}


def _synthesize_computation_invalid_release(
    *,
    out_rel: str,
) -> str:
    """Copy the valid computation release and overlay a rejected witness."""
    src_valid = repo_root() / "examples" / "computation-release"
    partial = repo_root() / "examples" / "computation-rejected-release"
    out_dir = repo_root() / out_rel
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(src_valid, out_dir)
    witness_src = partial / "computation_witness.json"
    if witness_src.is_file():
        shutil.copy2(witness_src, out_dir / "computation_witness.json")
    return out_rel


def _synthesize_tool_use_invalid_release(
    *,
    case_name: str,
    out_rel: str,
) -> str:
    """Copy the valid tool-use release and overlay invalid trace/certificate pair."""
    src_valid = repo_root() / "examples" / "tool-use-release"
    partial = repo_root() / "examples" / "tool-use-release-invalid" / case_name
    out_dir = repo_root() / out_rel
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(src_valid, out_dir)
    for name in ("tool_use_trace.json", "tool_use_trace.valid.json"):
        src = partial / name
        if src.is_file():
            shutil.copy2(src, out_dir / "tool_use_trace.json")
            shutil.copy2(src, out_dir / "tool_use_trace.valid.json")
            break
    for name in ("tool_use_certificate.json", "tool_use_certificate.valid.json"):
        src = partial / name
        if src.is_file():
            shutil.copy2(src, out_dir / "tool_use_certificate.json")
            shutil.copy2(src, out_dir / "tool_use_certificate.valid.json")
            break
    return out_rel


def _write_case_bundle(
    case_dir: Path,
    case: dict[str, Any],
    *,
    failure_manifest: dict[str, Any] | None = None,
    repair_hint: dict[str, Any] | None = None,
) -> None:
    _write_json(case_dir / "benchmark_case.v0.json", case)
    if failure_manifest is not None:
        _write_json(case_dir / "expected_failure.json", failure_manifest)
    if repair_hint is not None:
        _write_json(case_dir / "expected_repair_hint.json", repair_hint)


def _materialize_labtrust() -> None:
    root = repo_root() / "benchmarks" / "labtrust-qc-release"
    task_id = "labtrust-qc-release-v0"
    workflow = "labtrust.qc_release_v0.1"
    invalid_specs = [
        (
            "invalid-certificate-id",
            "invalid_certificate",
            "certificate_id_mismatch",
            "certificate_producer",
            "align_certificate_id",
            "Align trace_certificate certificate_id with bundle and verification.",
        ),
        (
            "invalid-trace-hash",
            "invalid_hash_mismatch",
            "trace_hash_mismatch",
            "hashing",
            "align_hash",
            "Align trace.json trace_hash with runtime receipt and certificate.",
        ),
        (
            "invalid-certified-bundle-hash",
            "invalid_hash_mismatch",
            "verified_input_hash_mismatch",
            "verifier",
            "align_hash",
            "Align verified_input.bundle_hash with certified bundle identity hash.",
        ),
        (
            "invalid-placeholder-commit",
            "invalid_registry",
            "placeholder_commit_detected",
            "runtime_producer",
            "align_provenance",
            "Replace placeholder commits with pinned release commits.",
        ),
        (
            "invalid-scientific-memory-import",
            "invalid_import",
            "scientific_memory_import_failed",
            "scientific_memory",
            "fix_import_report",
            "Set scientific_memory_import_report.verification_status to passed.",
        ),
    ]
    _write_json(
        root / "benchmark_task.v0.json",
        _benchmark_task(
            task_id=task_id,
            workflow_id=workflow,
            domain="process_safety",
            fixture_root="benchmarks/labtrust-qc-release",
            case_count=2 + len(invalid_specs),
        ),
    )
    _write_case_bundle(
        root / "valid" / "valid-release-chain",
        _benchmark_case(
            case_id="valid-release-chain",
            task_id=task_id,
            workflow_id=workflow,
            case_kind="valid_release",
            release_directory="examples/labtrust-release",
            expected_status="passed",
            expected_system_outcome="admitted",
            expected_failure_code=None,
            expected_responsible_component=None,
            expected_repair_hint_kind=None,
        ),
    )
    _write_case_bundle(
        root / "valid" / "valid-scientific-memory-import",
        _benchmark_case(
            case_id="valid-scientific-memory-import",
            task_id="scientific-memory-rendering-v0",
            workflow_id=workflow,
            case_kind="valid_release",
            release_directory="examples/labtrust-release",
            expected_status="passed",
            expected_system_outcome="admitted",
            expected_failure_code=None,
            expected_responsible_component=None,
            expected_repair_hint_kind=None,
        ),
    )
    invalid_map = {
        "invalid-certificate-id": "examples/labtrust-release-invalid/mismatched_certificate_id",
        "invalid-trace-hash": "examples/labtrust-release-invalid/mismatched_trace_hash",
        "invalid-certified-bundle-hash": "examples/labtrust-release-invalid/mismatched_certified_bundle_hash",
        "invalid-placeholder-commit": "examples/labtrust-release-invalid/placeholder_commit",
        "invalid-scientific-memory-import": "examples/labtrust-release-invalid/failed_scientific_memory_import",
    }
    for case_id, case_kind, code, component, hint_kind, message in invalid_specs:
        _write_case_bundle(
            root / "invalid" / case_id,
            _benchmark_case(
                case_id=case_id,
                task_id=task_id,
                workflow_id=workflow,
                case_kind=case_kind,
                release_directory=invalid_map[case_id],
                expected_status="failed",
                expected_system_outcome=_SYSTEM_OUTCOME_BY_CASE_KIND[case_kind],
                expected_failure_code=code,
                expected_responsible_component=component,
                expected_repair_hint_kind=hint_kind,
            ),
            failure_manifest=_expected_failure(
                case_id=case_id,
                task_id=task_id,
                failure_code=code,
                responsible_component=component,
                repair_hint_kind=hint_kind,
                message=message,
            ),
            repair_hint=_expected_repair_hint(hint_kind, message),
        )


def _materialize_tool_use() -> None:
    root = repo_root() / "benchmarks" / "tool-use-safety"
    task_id = "tool-use-safety-v0"
    workflow = "agent_tool_use.safety_v0"
    invalid_specs = [
        (
            "invalid-trace-hash",
            "invalid_hash_mismatch",
            "trace_hash_mismatch",
            "hashing",
            "align_hash",
            "Align tool_use trace_hash with certificate.",
        ),
        (
            "invalid-unauthorized-tool-call",
            "invalid_certificate",
            "unauthorized_tool_call",
            "runtime_producer",
            "align_provenance",
            "Remove or authorize tool calls flagged in the trace.",
        ),
        (
            "invalid-rejected-certificate",
            "invalid_certificate",
            "rejected_certificate",
            "certificate_producer",
            "align_certificate_id",
            "Certificate status must be CertificateChecked for release.",
        ),
    ]
    _write_json(
        root / "benchmark_task.v0.json",
        _benchmark_task(
            task_id=task_id,
            workflow_id=workflow,
            domain="agent_safety",
            fixture_root="benchmarks/tool-use-safety",
            case_count=1 + len(invalid_specs),
        ),
    )
    _write_case_bundle(
        root / "valid" / "valid-release-chain",
        _benchmark_case(
            case_id="valid-release-chain",
            task_id=task_id,
            workflow_id=workflow,
            case_kind="valid_release",
            release_directory="examples/tool-use-release",
            expected_status="passed",
            expected_system_outcome="admitted",
            expected_failure_code=None,
            expected_responsible_component=None,
            expected_repair_hint_kind=None,
        ),
    )
    invalid_map = {
        "invalid-trace-hash": _synthesize_tool_use_invalid_release(
            case_name="trace_hash_mismatch",
            out_rel="benchmarks/tool-use-safety/input_releases/invalid-trace-hash",
        ),
        "invalid-unauthorized-tool-call": _synthesize_tool_use_invalid_release(
            case_name="unauthorized_tool_call",
            out_rel="benchmarks/tool-use-safety/input_releases/invalid-unauthorized-tool-call",
        ),
        "invalid-rejected-certificate": _synthesize_tool_use_invalid_release(
            case_name="rejected_certificate",
            out_rel="benchmarks/tool-use-safety/input_releases/invalid-rejected-certificate",
        ),
    }
    for case_id, case_kind, code, component, hint_kind, message in invalid_specs:
        _write_case_bundle(
            root / "invalid" / case_id,
            _benchmark_case(
                case_id=case_id,
                task_id=task_id,
                workflow_id=workflow,
                case_kind=case_kind,
                release_directory=invalid_map[case_id],
                expected_status="failed",
                expected_system_outcome=_SYSTEM_OUTCOME_BY_CASE_KIND[case_kind],
                expected_failure_code=code,
                expected_responsible_component=component,
                expected_repair_hint_kind=hint_kind,
            ),
            failure_manifest=_expected_failure(
                case_id=case_id,
                task_id=task_id,
                failure_code=code,
                responsible_component=component,
                repair_hint_kind=hint_kind,
                message=message,
            ),
            repair_hint=_expected_repair_hint(hint_kind, message),
        )


def _materialize_computation() -> None:
    root = repo_root() / "benchmarks" / "computation-reproducibility"
    task_id = "computation-reproducibility-v0"
    workflow = "scientific_computation.reproducibility_v0"
    invalid_specs = [
        (
            "invalid-witness-hash",
            "invalid_certificate",
            "rejected_computation_witness",
            "certificate_producer",
            "align_certificate_id",
            "Computation witness status must be CertificateChecked for release.",
        ),
    ]
    _write_json(
        root / "benchmark_task.v0.json",
        _benchmark_task(
            task_id=task_id,
            workflow_id=workflow,
            domain="scientific_computation",
            fixture_root="benchmarks/computation-reproducibility",
            case_count=1 + len(invalid_specs),
        ),
    )
    _write_case_bundle(
        root / "valid" / "valid-release-chain",
        _benchmark_case(
            case_id="valid-release-chain",
            task_id=task_id,
            workflow_id=workflow,
            case_kind="valid_release",
            release_directory="examples/computation-release",
            expected_status="passed",
            expected_system_outcome="admitted",
            expected_failure_code=None,
            expected_responsible_component=None,
            expected_repair_hint_kind=None,
        ),
    )
    invalid_map = {
        "invalid-witness-hash": _synthesize_computation_invalid_release(
            out_rel="benchmarks/computation-reproducibility/input_releases/invalid-witness-hash",
        ),
    }
    for case_id, case_kind, code, component, hint_kind, message in invalid_specs:
        _write_case_bundle(
            root / "invalid" / case_id,
            _benchmark_case(
                case_id=case_id,
                task_id=task_id,
                workflow_id=workflow,
                case_kind=case_kind,
                release_directory=invalid_map[case_id],
                expected_status="failed",
                expected_system_outcome=_SYSTEM_OUTCOME_BY_CASE_KIND[case_kind],
                expected_failure_code=code,
                expected_responsible_component=component,
                expected_repair_hint_kind=hint_kind,
            ),
            failure_manifest=_expected_failure(
                case_id=case_id,
                task_id=task_id,
                failure_code=code,
                responsible_component=component,
                repair_hint_kind=hint_kind,
                message=message,
            ),
            repair_hint=_expected_repair_hint(hint_kind, message),
        )


def _materialize_cross_domain() -> None:
    root = repo_root() / "benchmarks" / "cross-domain"
    task_id = "cross-domain-release-chain-v0"
    valid_cases = [
        ("valid-labtrust-release", "labtrust.qc_release_v0.1", "examples/labtrust-release"),
        ("valid-tool-use-release", "agent_tool_use.safety_v0", "examples/tool-use-release"),
        (
            "valid-computation-release",
            "scientific_computation.reproducibility_v0",
            "examples/computation-release",
        ),
    ]
    _write_json(
        root / "benchmark_task.v0.json",
        _benchmark_task(
            task_id=task_id,
            workflow_id="labtrust.qc_release_v0.1",
            domain="cross_domain",
            fixture_root="benchmarks/cross-domain",
            case_count=len(valid_cases),
        ),
    )
    for case_id, workflow_id, release_directory in valid_cases:
        _write_case_bundle(
            root / "valid" / case_id,
            _benchmark_case(
                case_id=case_id,
                task_id=task_id,
                workflow_id=workflow_id,
                case_kind="valid_release",
                release_directory=release_directory,
                expected_status="passed",
                expected_system_outcome="admitted",
                expected_failure_code=None,
                expected_responsible_component=None,
                expected_repair_hint_kind=None,
            ),
        )
    formal_cases = [
        ("formal-labtrust-lean-check", "examples/labtrust-release"),
        ("formal-tool-use-lean-check", "examples/tool-use-release"),
        ("formal-computation-lean-check", "examples/computation-release"),
    ]
    for case_id, release_directory in formal_cases:
        _write_case_bundle(
            root / "valid" / case_id,
            _benchmark_case(
                case_id=case_id,
                task_id="formal-trust-kernel-v0",
                workflow_id="cross-domain",
                case_kind="valid_release",
                release_directory=release_directory,
                expected_status="passed",
                expected_system_outcome="admitted",
                expected_failure_code=None,
                expected_responsible_component=None,
                expected_repair_hint_kind=None,
            ),
        )


def main() -> int:
    _materialize_labtrust()
    _materialize_tool_use()
    _materialize_computation()
    _materialize_cross_domain()

    registry_path = examples_dir() / "benchmark_registry.valid.json"
    _write_json(registry_path, build_benchmark_registry())
    validate_file(registry_path)

    artifact_registry_path = examples_dir() / "artifact_registry.valid.json"
    _write_json(artifact_registry_path, build_artifact_registry())
    validate_file(artifact_registry_path)

    from pcs_core.shared_hash_vectors import write_shared_vectors

    write_shared_vectors(force=True)

    primary_report_alias = {
        "benchmarks/labtrust-qc-release": "labtrust-qc-release-v0",
        "benchmarks/tool-use-safety": "tool-use-safety-v0",
        "benchmarks/computation-reproducibility": "computation-reproducibility-v0",
        "benchmarks/cross-domain": "cross-domain-release-chain-v0",
    }
    for suite_id in (
        "labtrust-qc-release-v0",
        "tool-use-safety-v0",
        "computation-reproducibility-v0",
        "cross-domain-release-chain-v0",
        "formal-trust-kernel-v0",
        "scientific-memory-rendering-v0",
    ):
        registry = build_benchmark_registry()
        fixture_root = registry["suites"][suite_id]["fixture_root"]
        expected_reports = repo_root() / fixture_root / "expected_reports"
        expected_reports.mkdir(parents=True, exist_ok=True)
        report = run_benchmark_suite(suite_id)
        report_path = expected_reports / f"benchmark_report.{suite_id}.v0.json"
        _write_json(report_path, report)
        validate_file(report_path)
        if primary_report_alias.get(fixture_root) == suite_id:
            _write_json(expected_reports / "benchmark_report.v0.json", report)
            validate_file(expected_reports / "benchmark_report.v0.json")

    import subprocess
    import sys

    examples_script = Path(__file__).resolve().parent / "materialize_benchmark_examples.py"
    producer_script = Path(__file__).resolve().parent / "materialize_benchmark_producer_examples.py"
    subprocess.run([sys.executable, str(examples_script)], check=True)
    subprocess.run([sys.executable, str(producer_script)], check=True)

    for rel in (
        "benchmarks/labtrust-qc-release/benchmark_task.v0.json",
        "benchmarks/labtrust-qc-release/valid/valid-release-chain/benchmark_case.v0.json",
        "benchmarks/labtrust-qc-release/invalid/invalid-certificate-id/benchmark_case.v0.json",
    ):
        validate_file(repo_root() / rel)

    print("Wrote benchmark fixtures and examples/benchmark_registry.valid.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
