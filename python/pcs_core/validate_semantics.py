"""Semantic validation orchestration and public validate API."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pcs_core.paths import examples_dir as default_examples_dir
from pcs_core.paths import repo_root, schemas_dir
from pcs_core.registry_data import PF_CORE_CLAIM_CLASSES
from pcs_core.validate_pf_core import _validate_pfcore_claim_class
from pcs_core.status import ARTIFACT_STATUSES, TRACE_CERTIFICATE_STATUSES

from pcs_core.lean_validate import (
    validate_lean_check_result_semantics,
    validate_proof_obligation_semantics,
)
from pcs_core.protocol_validate import (
    validate_artifact_registry_semantics,
    validate_conformance_report_semantics,
    validate_handoff_manifest_semantics,
    validate_release_chain_validation_result_semantics,
    validate_release_manifest_fixture_refs,
    validate_release_manifest_semantics,
)
from pcs_core.tool_use_validate import (
    validate_tool_use_certificate_semantics,
    validate_tool_use_trace_semantics,
    validate_workflow_profile_semantics,
)
from pcs_core.computation_validate import (
    validate_computation_run_receipt_semantics,
    validate_computation_witness_semantics,
    validate_dataset_receipt_semantics,
    validate_environment_receipt_semantics,
    validate_result_artifact_semantics,
)
from pcs_core.benchmark_validate import (
    validate_benchmark_case_semantics,
    validate_benchmark_metric_registry_semantics,
    validate_benchmark_registry_semantics,
    validate_benchmark_report_semantics,
    validate_benchmark_run_semantics,
    validate_benchmark_suite_manifest_semantics,
    validate_benchmark_task_semantics,
)
from pcs_core.validate_detect import (
    ARTIFACT_SCHEMAS,
    ValidationError,
    detect_artifact_type,
    get_validator,
    validate_schema,
    _load_schema,
)
from pcs_core.validate_pcs_core import (
    _check_source_commits,
    _validate_science_claim_bundle,
    _validate_signed_bundle,
    _validate_status_fields,
    _validate_verification_result,
)
from pcs_core.validate_pf_core import (
    _PF_CORE_ARTIFACT_TYPES,
    _validate_lean_check_result,
    _validate_pfcore_certificate,
    _validate_pfcore_claim_class,
    _validate_pfcore_trace,
)

def validate_semantics(data: dict[str, Any], artifact_type: str) -> list[str]:
    errors: list[str] = []

    if artifact_type == "ArtifactRegistry.v0":
        errors.extend(validate_artifact_registry_semantics(data))
        return errors

    if artifact_type == "ComponentReleaseFragment.v0":
        _check_source_commits(data, "", errors)
        return errors

    if artifact_type == "MigrationReport.v0":
        return errors

    if artifact_type == "ReleaseManifest.v0":
        errors.extend(validate_release_manifest_semantics(data))
        return errors

    if artifact_type == "HandoffManifest.v0":
        errors.extend(validate_handoff_manifest_semantics(data))
        return errors

    if artifact_type == "ConformanceReport.v0":
        errors.extend(validate_conformance_report_semantics(data))
        return errors

    if artifact_type == "WorkflowProfile.v0":
        errors.extend(validate_workflow_profile_semantics(data))
        return errors

    if artifact_type == "ToolUseTrace.v0":
        errors.extend(validate_tool_use_trace_semantics(data))
        return errors

    if artifact_type == "ToolUseCertificate.v0":
        errors.extend(validate_tool_use_certificate_semantics(data))
        return errors

    if artifact_type == "DatasetReceipt.v0":
        errors.extend(validate_dataset_receipt_semantics(data))
        return errors

    if artifact_type == "EnvironmentReceipt.v0":
        errors.extend(validate_environment_receipt_semantics(data))
        return errors

    if artifact_type == "ComputationRunReceipt.v0":
        errors.extend(validate_computation_run_receipt_semantics(data))
        return errors

    if artifact_type == "ResultArtifact.v0":
        errors.extend(validate_result_artifact_semantics(data))
        return errors

    if artifact_type == "ComputationWitness.v0":
        errors.extend(validate_computation_witness_semantics(data))
        return errors

    if artifact_type == "ProofObligation.v0":
        errors.extend(validate_proof_obligation_semantics(data))
        return errors

    if artifact_type == "LeanCheckResult.v0":
        if data.get("artifact_type") == "LeanCheckResult.v0":
            errors.extend(_validate_lean_check_result(data))
        elif "check_id" in data:
            errors.extend(validate_lean_check_result_semantics(data))
        else:
            errors.append(
                "LeanCheckResult.v0: expected PF-Core artifact_type or PCS check_id shape"
            )
        return errors


    if artifact_type == "BenchmarkMetricRegistry.v0":
        errors.extend(validate_benchmark_metric_registry_semantics(data))
        return errors

    if artifact_type == "BenchmarkRegistry.v0":
        errors.extend(validate_benchmark_registry_semantics(data))
        return errors

    if artifact_type == "BenchmarkSuiteManifest.v0":
        errors.extend(validate_benchmark_suite_manifest_semantics(data))
        return errors

    if artifact_type == "BenchmarkTask.v0":
        errors.extend(validate_benchmark_task_semantics(data))
        return errors

    if artifact_type == "BenchmarkCase.v0":
        errors.extend(validate_benchmark_case_semantics(data))
        return errors

    if artifact_type == "BenchmarkRun.v0":
        errors.extend(validate_benchmark_run_semantics(data))
        return errors

    if artifact_type == "BenchmarkReport.v0":
        errors.extend(validate_benchmark_report_semantics(data))
        return errors

    if artifact_type == "MetricSummary.v0":
        return errors

    if artifact_type == "BenchmarkArtifactRef.v0":
        from pcs_core.benchmark_validate import validate_benchmark_artifact_ref_semantics

        errors.extend(validate_benchmark_artifact_ref_semantics(data))
        return errors

    if artifact_type == "PcsBenchIngest.v0":
        from pcs_core.benchmark_validate import validate_pcs_bench_ingest_semantics

        errors.extend(validate_pcs_bench_ingest_semantics(data))
        return errors

    if artifact_type == "ConformanceRun.v0":
        return errors

    if artifact_type == "FailureCaseManifest.v0":
        return errors

    if artifact_type == "FailureLocalizationResult.v0":
        return errors

    if artifact_type == "CoverageReport.v0":
        return errors

    if artifact_type == "ExplainQualityReport.v0":
        return errors

    if artifact_type == "ProfileCoverageReport.v0":
        return errors

    if artifact_type == "ReleaseChainValidationResult.v0":
        errors.extend(validate_release_chain_validation_result_semantics(data))
        checks = data.get("checks")
        if isinstance(checks, list):
            for index, check in enumerate(checks):
                if isinstance(check, dict):
                    _validate_status_fields(check, f"checks[{index}]", errors)
        return errors

    _check_source_commits(data, "", errors)
    _validate_status_fields(data, "", errors)

    if artifact_type == "ClaimArtifact.v0":
        ref = data.get("assumption_set_ref")
        if not ref or not str(ref).strip():
            errors.append("ClaimArtifact.v0 requires non-empty assumption_set_ref")

    if artifact_type == "ScienceClaimBundle.v0":
        errors.extend(_validate_science_claim_bundle(data))

    if artifact_type == "VerificationResult.v0":
        errors.extend(_validate_verification_result(data))

    if artifact_type == "SignedScienceClaimBundle.v0":
        errors.extend(_validate_signed_bundle(data))

    if artifact_type == "TraceCertificate.v0":
        status = str(data.get("status") or "")
        if status and status not in TRACE_CERTIFICATE_STATUSES:
            errors.append(f"TraceCertificate.v0 invalid status {status!r}")

    if artifact_type == "PFCoreTrace.v0":
        errors.extend(_validate_pfcore_trace(data))

    if artifact_type == "PFCoreContract.v0":
        from pcs_core.pf_core_contract import validate_pfcore_contract_semantics

        errors.extend(validate_pfcore_contract_semantics(data))

    if artifact_type == "PFCoreCertificate.v0":
        errors.extend(_validate_pfcore_certificate(data))

    if artifact_type == "LeanCheckResult.v0":
        errors.extend(_validate_lean_check_result(data))

    if artifact_type in _PF_CORE_ARTIFACT_TYPES and artifact_type not in {
        "PFCoreTrace.v0",
        "PFCoreCertificate.v0",
        "LeanCheckResult.v0",
        "ToolUseTrace.v0",
    }:
        _validate_pfcore_claim_class(
            data, "root", errors, allowed=PF_CORE_CLAIM_CLASSES, artifact_kind="pf-core"
        )

    return errors


def validate_artifact(data: dict[str, Any], artifact_type: str | None = None) -> None:
    artifact_type = artifact_type or detect_artifact_type(data)
    if not artifact_type:
        raise ValidationError("Could not detect artifact type from JSON content")

    schema_errors = validate_schema(data, artifact_type)
    semantic_errors = validate_semantics(data, artifact_type)
    all_errors = schema_errors + semantic_errors
    if all_errors:
        raise ValidationError(
            f"Validation failed for {artifact_type}",
            errors=all_errors,
        )


def validate_file(path: Path | str) -> str:
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValidationError("Artifact root must be a JSON object")
    artifact_type = detect_artifact_type(data)
    if not artifact_type:
        raise ValidationError(f"Could not detect artifact type in {path}")
    validate_artifact(data, artifact_type)
    if artifact_type == "ReleaseManifest.v0":
        ref_errors = validate_release_manifest_fixture_refs(data, path.parent)
        if ref_errors:
            raise ValidationError(
                f"Validation failed for {artifact_type}",
                errors=ref_errors,
            )
    return artifact_type


def _is_valid_example(path: Path) -> bool:
    if "tool-use-release-invalid" in path.parts or "computation-release-invalid" in path.parts:
        return False
    return path.suffix == ".json" and ".valid." in path.name


def iter_example_json_files(examples_dir: Path) -> list[Path]:
    return sorted(p for p in examples_dir.rglob("*.json") if p.is_file())


def check_all_schemas() -> None:
    from jsonschema import Draft202012Validator

    from pcs_core.validate_detect import ARTIFACT_SCHEMAS, get_validator, _load_schema
    from pcs_core.paths import schemas_dir

    for artifact_type, schema_name in ARTIFACT_SCHEMAS.items():
        schema_path = schemas_dir() / schema_name
        schema = _load_schema(schema_path)
        Draft202012Validator.check_schema(schema)
        get_validator(artifact_type)


def check_valid_examples(examples_dir: Path | None = None) -> None:
    examples_dir = examples_dir or default_examples_dir()
    for path in iter_example_json_files(examples_dir):
        if _is_valid_example(path):
            validate_file(path)
    for name in (
        "release_manifest.valid.json",
        "handoff_manifest.valid.json",
        "release_chain_validation_result.valid.json",
        "artifact_registry.valid.json",
        "migration_report.valid.json",
        "proof_obligation.valid.json",
        "lean_check_result.valid.json",
        "benchmark_registry.valid.json",
        "benchmark_metric_registry.valid.json",
    ):
        validate_file(examples_dir / name)

    benchmarks_examples = examples_dir / "benchmarks"
    if benchmarks_examples.is_dir():
        for path in sorted(benchmarks_examples.rglob("*.valid.json")):
            validate_file(path)
        compat = benchmarks_examples / "compatibility"
        if compat.is_dir():
            for path in sorted(compat.glob("*.normalized.json")) + sorted(
                compat.glob("*.pcs_bench_ingest.normalized.json"),
            ):
                validate_file(path)

    producer_examples = examples_dir / "benchmark"
    if producer_examples.is_dir():
        for path in sorted(producer_examples.glob("*.valid.json")):
            validate_file(path)

    ingest_examples = examples_dir / "benchmark_ingest"
    if ingest_examples.is_dir():
        for path in sorted(ingest_examples.glob("*.pcs_bench_ingest.valid.json")):
            validate_file(path)

    check_pf_core_valid_fixtures()

def check_invalid_examples(examples_dir: Path | None = None) -> None:
    examples_dir = examples_dir or default_examples_dir()
    invalid_cases: dict[str, str | None] = {
        "invalid_unknown_status.json": "RuntimeReceipt.v0",
        "invalid_missing_assumption_set.json": "ScienceClaimBundle.v0",
        "invalid_mismatched_trace_hash.json": "ScienceClaimBundle.v0",
        "invalid_zero_source_commit.release.json": "RuntimeReceipt.v0",
        "labtrust/invalid_singular_runtime_receipt_bundle.json": "ScienceClaimBundle.v0",
        "labtrust/invalid_signed_schema_version_artifact_name.json": "SignedScienceClaimBundle.v0",
        "labtrust/invalid_failed_verification_result.json": "VerificationResult.v0",
        "labtrust/invalid_missing_trace_certificate.json": "ScienceClaimBundle.v0",
    }
    for filename, artifact_type in invalid_cases.items():
        path = examples_dir / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        detected = detect_artifact_type(data)
        use_type = artifact_type or detected
        if not use_type:
            raise ValidationError(f"Could not detect type for {filename}")
        schema_errors = validate_schema(data, use_type)
        semantic_errors = validate_semantics(data, use_type)
        if not schema_errors and not semantic_errors:
            raise ValidationError(f"Expected {filename} to fail validation")
    check_pf_core_invalid_fixtures()
