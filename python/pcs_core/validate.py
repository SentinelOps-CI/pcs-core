"""JSON Schema and semantic validation for PCS artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from pcs_core.paths import examples_dir as default_examples_dir
from pcs_core.paths import repo_root, schemas_dir
from pcs_core.registry_data import PF_CORE_CLAIM_CLASSES
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
ARTIFACT_SCHEMAS: dict[str, str] = {
    "AssumptionSet.v0": "AssumptionSet.v0.schema.json",
    "SourceSpan.v0": "SourceSpan.v0.schema.json",
    "ClaimArtifact.v0": "ClaimArtifact.v0.schema.json",
    "RuntimeReceipt.v0": "RuntimeReceipt.v0.schema.json",
    "TraceCertificate.v0": "TraceCertificate.v0.schema.json",
    "EvidenceBundle.v0": "EvidenceBundle.v0.schema.json",
    "ScienceClaimBundle.v0": "ScienceClaimBundle.v0.schema.json",
    "VerificationResult.v0": "VerificationResult.v0.schema.json",
    "SignedScienceClaimBundle.v0": "SignedScienceClaimBundle.v0.schema.json",
    "ReleaseManifest.v0": "ReleaseManifest.v0.schema.json",
    "HandoffManifest.v0": "HandoffManifest.v0.schema.json",
    "ReleaseChainValidationResult.v0": "ReleaseChainValidationResult.v0.schema.json",
    "ArtifactRegistry.v0": "ArtifactRegistry.v0.schema.json",
    "MigrationReport.v0": "MigrationReport.v0.schema.json",
    "ComponentReleaseFragment.v0": "ComponentReleaseFragment.v0.schema.json",
    "SemanticCheckExecution.v0": "SemanticCheckExecution.v0.schema.json",
    "ConformanceReport.v0": "ConformanceReport.v0.schema.json",
    "WorkflowProfile.v0": "WorkflowProfile.v0.schema.json",
    "ToolUseTrace.v0": "ToolUseTrace.v0.schema.json",
    "ToolUseCertificate.v0": "ToolUseCertificate.v0.schema.json",
    "DatasetReceipt.v0": "DatasetReceipt.v0.schema.json",
    "EnvironmentReceipt.v0": "EnvironmentReceipt.v0.schema.json",
    "ComputationRunReceipt.v0": "ComputationRunReceipt.v0.schema.json",
    "ResultArtifact.v0": "ResultArtifact.v0.schema.json",
    "ComputationWitness.v0": "ComputationWitness.v0.schema.json",
    "ProofObligation.v0": "ProofObligation.v0.schema.json",
    "LeanCheckResult.v0": "LeanCheckResult.v0.schema.json",
    "BenchmarkTask.v0": "BenchmarkTask.v0.schema.json",
    "BenchmarkCase.v0": "BenchmarkCase.v0.schema.json",
    "BenchmarkRun.v0": "BenchmarkRun.v0.schema.json",
    "BenchmarkReport.v0": "BenchmarkReport.v0.schema.json",
    "BenchmarkRegistry.v0": "BenchmarkRegistry.v0.schema.json",
    "BenchmarkSuiteManifest.v0": "BenchmarkSuiteManifest.v0.schema.json",
    "ConformanceRun.v0": "ConformanceRun.v0.schema.json",
    "FailureCaseManifest.v0": "FailureCaseManifest.v0.schema.json",
    "FailureLocalizationResult.v0": "FailureLocalizationResult.v0.schema.json",
    "CoverageReport.v0": "CoverageReport.v0.schema.json",
    "ExplainQualityReport.v0": "ExplainQualityReport.v0.schema.json",
    "ProfileCoverageReport.v0": "ProfileCoverageReport.v0.schema.json",
    "BenchmarkMetricRegistry.v0": "BenchmarkMetricRegistry.v0.schema.json",
    "MetricSummary.v0": "MetricSummary.v0.schema.json",
    "PcsBenchIngest.v0": "PcsBenchIngest.v0.schema.json",
    "BenchmarkArtifactRef.v0": "BenchmarkArtifactRef.v0.schema.json",
    "PFCorePrincipal.v0": "PFCorePrincipal.v0.schema.json",
    "PFCoreCapability.v0": "PFCoreCapability.v0.schema.json",
    "PFCoreResource.v0": "PFCoreResource.v0.schema.json",
    "PFCoreAction.v0": "PFCoreAction.v0.schema.json",
    "PFCoreEffect.v0": "PFCoreEffect.v0.schema.json",
    "PFCoreDecision.v0": "PFCoreDecision.v0.schema.json",
    "PFCoreEvent.v0": "PFCoreEvent.v0.schema.json",
    "PFCoreTrace.v0": "PFCoreTrace.v0.schema.json",
    "PFCoreContract.v0": "PFCoreContract.v0.schema.json",
    "PFCoreHandoff.v0": "PFCoreHandoff.v0.schema.json",
    "PFCoreRuntimeObservation.v0": "PFCoreRuntimeObservation.v0.schema.json",
    "PFCoreCertificate.v0": "PFCoreCertificate.v0.schema.json",
    "PCSBridgeCertificate.v0": "PCSBridgeCertificate.v0.schema.json",
}

CERTIFIED_CLAIM_STATUSES = frozenset(
    {
        "CertificateChecked",
        "ProofChecked",
        "RuntimeChecked",
    }
)

IMPORT_READY_VERIFICATION_STATUSES = frozenset(
    {
        "ProofChecked",
        "CertificateChecked",
        "RuntimeChecked",
    }
)

_ZERO_COMMIT_RE = re.compile(r"^0+$")


class ValidationError(Exception):
    """Raised when artifact validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


_PF_CORE_ARTIFACT_TYPES = frozenset(
    key for key in ARTIFACT_SCHEMAS if key.startswith("PFCore") or key == "ToolUseTrace.v0"
)

LEAN_CHECK_RESULT_STATUSES = frozenset(
    {
        "DecidersPassed",
        "LeanProofChecked",
        "ReplayValidated",
        "Rejected",
        "Stale",
    }
)

_ZERO_COMMIT_RE = re.compile(r"^0+$")


def _resolve_schema_ref(schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if ref.startswith("pf_core.defs.json#/$defs/"):
        defs_path = schemas_dir() / "pf_core.defs.json"
        defs_schema = _load_schema(defs_path)
        def_name = ref.split("/")[-1]
        target = defs_schema.get("$defs", {}).get(def_name)
        if isinstance(target, dict):
            return target
    return {}


def _schema_requires_artifact_type(artifact_type: str) -> bool:
    schema_name = ARTIFACT_SCHEMAS.get(artifact_type)
    if not schema_name:
        return False
    schema = _load_schema(schemas_dir() / schema_name)
    if "$ref" in schema:
        ref = str(schema["$ref"])
        if ref.endswith("embedded_event") and artifact_type == "PFCoreEvent.v0":
            return True
        resolved = _resolve_schema_ref(schema, ref)
        if resolved:
            schema = resolved
    props = schema.get("properties")
    if not isinstance(props, dict):
        return False
    artifact_type_schema = props.get("artifact_type")
    if not isinstance(artifact_type_schema, dict):
        return False
    return artifact_type_schema.get("const") == artifact_type



def detect_artifact_type(data: dict[str, Any]) -> str | None:
    explicit = data.get("artifact_type")
    if isinstance(explicit, str) and explicit in ARTIFACT_SCHEMAS:
        if _schema_requires_artifact_type(explicit):
            return explicit
        if explicit == "LeanCheckResult.v0" and data.get("schema_version") == "v0":
            if "trace_path" in data or "check_id" in data:
                return explicit
    if (
        "trace_id" in data
        and "tool_calls" in data
        and "workflow_id" in data
        and "agent_id" in data
        and data.get("schema_version") == "v0"
        and "artifact_type" not in data
    ):
        return "ToolUseTrace.v0"
    if "signed_bundle_id" in data and "science_claim_bundle" in data:
        return "SignedScienceClaimBundle.v0"
    if "bundle_id" in data and "claim_artifact" in data:
        return "ScienceClaimBundle.v0"
    if "verification_id" in data:
        return "VerificationResult.v0"
    if "receipt_id" in data:
        return "RuntimeReceipt.v0"
    if "certificate_id" in data:
        return "TraceCertificate.v0"
    if "assumption_set_id" in data:
        return "AssumptionSet.v0"
    if "source_span_id" in data:
        return "SourceSpan.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("registry_id"), str)
        and isinstance(data.get("metrics"), dict)
        and "registry_version" in data
        and "suites" not in data
    ):
        return "BenchmarkMetricRegistry.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("registry_id"), str)
        and isinstance(data.get("suites"), dict)
        and "registry_version" in data
    ):
        return "BenchmarkRegistry.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("suite_id"), str)
        and isinstance(data.get("case_ids"), list)
        and isinstance(data.get("cases"), list)
        and "case_count" in data
        and "task_id" in data
    ):
        return "BenchmarkSuiteManifest.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("report_id"), str)
        and isinstance(data.get("required_sections"), list)
        and "quality_score" in data
    ):
        return "ExplainQualityReport.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("coverage_id"), str)
        and isinstance(data.get("workflow_profile_id"), str)
        and isinstance(data.get("artifact_types_required"), list)
    ):
        return "ProfileCoverageReport.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("artifact_type"), str)
        and isinstance(data.get("path"), str)
        and isinstance(data.get("sha256"), str)
        and isinstance(data.get("role"), str)
        and "producer_id" not in data
        and "benchmark_runs" not in data
    ):
        return "BenchmarkArtifactRef.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("producer_id"), str)
        and isinstance(data.get("suite_id"), str)
        and isinstance(data.get("benchmark_runs"), list)
        and isinstance(data.get("logs"), list)
        and "workflow_id" in data
    ):
        return "PcsBenchIngest.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("metric_id"), str)
        and "applicability" in data
        and "score" in data
        and "numerator" in data
        and "benchmark_suite_id" not in data
    ):
        return "MetricSummary.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("report_id"), str)
        and isinstance(data.get("benchmark_suite_id"), str)
        and isinstance(data.get("summary"), dict)
    ):
        return "BenchmarkReport.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("run_id"), str)
        and isinstance(data.get("case_id"), str)
        and "duration_ms" in data
        and "observed_status" in data
    ):
        return "BenchmarkRun.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("case_id"), str)
        and isinstance(data.get("case_kind"), str)
        and "input_artifacts" in data
    ):
        return "BenchmarkCase.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("task_id"), str)
        and isinstance(data.get("metrics"), list)
        and "success_criteria" in data
    ):
        return "BenchmarkTask.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("coverage_id"), str)
        and "coverage_ratio" in data
        and "numerator" in data
        and ("metric" in data or "metric_id" in data)
    ):
        return "CoverageReport.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("result_id"), str)
        and "localized_correctly" in data
    ):
        return "FailureLocalizationResult.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("manifest_id"), str)
        and isinstance(data.get("failure_code"), str)
        and "repair_hint_kind" in data
    ):
        return "FailureCaseManifest.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("run_id"), str)
        and isinstance(data.get("suite"), str)
        and "started_at" in data
        and "completed_at" in data
    ):
        return "ConformanceRun.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("suite"), str)
        and "checks_passed" in data
        and "checks_failed" in data
        and isinstance(data.get("failures"), list)
    ):
        return "ConformanceReport.v0"
    if (
        "policy_id" in data
        and "severity_definitions" in data
        and isinstance(data.get("checks"), list)
    ):
        return "SemanticCheckExecution.v0"
    if (
        "from_version" in data
        and "to_version" in data
        and "changes" in data
        and "artifact_type" in data
    ):
        return "MigrationReport.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("check_id"), str)
        and isinstance(data.get("proof_obligation_id"), str)
        and "lean_theorem" in data
        and "lean_version" in data
    ):
        return "LeanCheckResult.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("obligation_id"), str)
        and isinstance(data.get("obligations"), list)
        and "lean_module" in data
    ):
        return "ProofObligation.v0"
    if "validation_id" in data and "artifacts_checked" in data:
        return "ReleaseChainValidationResult.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("component"), str)
        and isinstance(data.get("artifacts"), dict)
        and "signature_or_digest" in data
        and "source_commit" in data
    ):
        return "ComponentReleaseFragment.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("workflow_id"), str)
        and isinstance(data.get("domain"), str)
        and isinstance(data.get("handoff_sequence"), list)
        and isinstance(data.get("runtime_artifacts"), list)
    ):
        return "WorkflowProfile.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("witness_id"), str)
        and isinstance(data.get("dataset_hash"), str)
        and isinstance(data.get("run_receipt_hash"), str)
    ):
        return "ComputationWitness.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("dataset_id"), str)
        and isinstance(data.get("aggregate_hash"), str)
        and isinstance(data.get("files"), list)
    ):
        return "DatasetReceipt.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("environment_id"), str)
        and isinstance(data.get("environment_kind"), str)
    ):
        return "EnvironmentReceipt.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("run_id"), str)
        and isinstance(data.get("command"), str)
        and "dataset_receipt_ref" in data
    ):
        return "ComputationRunReceipt.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("result_id"), str)
        and isinstance(data.get("result_kind"), str)
    ):
        return "ResultArtifact.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("trace_id"), str)
        and isinstance(data.get("tool_calls"), list)
    ):
        return "ToolUseTrace.v0"
    if "handoff_id" in data and "handoff_kind" in data:
        return "HandoffManifest.v0"
    if "registry_id" in data and "entries" in data and "registry_version" in data:
        return "ArtifactRegistry.v0"
    if (
        "release_id" in data
        and "producer_repos" in data
        and "validation_profile" in data
        and "workflow_profile_id" in data
    ):
        return "ReleaseManifest.v0"
    if "signed_bundle_id" in data and "science_claim_bundle" in data:
        return "SignedScienceClaimBundle.v0"
    if "bundle_id" in data and "claim_artifact" in data:
        return "ScienceClaimBundle.v0"
    if "verification_id" in data:
        return "VerificationResult.v0"
    if "receipt_id" in data:
        return "RuntimeReceipt.v0"
    if (
        data.get("schema_version") == "v0"
        and isinstance(data.get("certificate_id"), str)
        and "policy_hash" in data
        and isinstance(data.get("violations"), list)
        and "spec_hash" not in data
    ):
        return "ToolUseCertificate.v0"
    if "certificate_id" in data:
        return "TraceCertificate.v0"
    if "assumption_set_id" in data:
        return "AssumptionSet.v0"
    if "source_span_id" in data:
        return "SourceSpan.v0"
    if data.get("artifact_type") == "ClaimArtifact.v0":
        return "ClaimArtifact.v0"
    if "bundle_id" in data and "claim_refs" in data:
        return "EvidenceBundle.v0"
    return None



def _load_schema(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_registry() -> Registry:
    schema_root = schemas_dir()
    resources: list[tuple[str, Resource]] = []
    for path in sorted(schema_root.glob("*.json")):
        schema = _load_schema(path)
        schema_id = schema.get("$id")
        if schema_id:
            resources.append(
                (schema_id, Resource.from_contents(schema, default_specification=DRAFT202012))
            )
        file_uri = path.as_uri()
        resources.append(
            (file_uri, Resource.from_contents(schema, default_specification=DRAFT202012))
        )
        resources.append(
            (path.name, Resource.from_contents(schema, default_specification=DRAFT202012))
        )
    return Registry().with_resources(resources)


_REGISTRY: Registry | None = None


def get_registry() -> Registry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = build_registry()
    return _REGISTRY


def get_validator(artifact_type: str) -> Draft202012Validator:
    schema_name = ARTIFACT_SCHEMAS.get(artifact_type)
    if not schema_name:
        raise ValidationError(f"Unknown artifact type: {artifact_type}")
    schema_path = schemas_dir() / schema_name
    schema = _load_schema(schema_path)
    return Draft202012Validator(schema, registry=get_registry())


def validate_schema(data: dict[str, Any], artifact_type: str) -> list[str]:
    validator = get_validator(artifact_type)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [e.message for e in errors]


def _is_zero_source_commit(value: str) -> bool:
    return bool(_ZERO_COMMIT_RE.match(value.strip()))


def _local_dev_enabled(obj: dict[str, Any], inherited: bool) -> bool:
    if inherited:
        return True
    if obj.get("local_dev") is True:
        return True
    return False


def _check_source_commits(
    obj: Any,
    path: str,
    errors: list[str],
    *,
    inherited_local_dev: bool = False,
) -> None:
    if isinstance(obj, dict):
        local_dev = _local_dev_enabled(obj, inherited_local_dev)
        commit = obj.get("source_commit")
        if isinstance(commit, str) and _is_zero_source_commit(commit) and not local_dev:
            errors.append(
                f"{path or 'root'}: zero source_commit not allowed without local_dev=true"
            )
        for key, value in obj.items():
            child = f"{path}.{key}" if path else key
            _check_source_commits(value, child, errors, inherited_local_dev=local_dev)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _check_source_commits(
                item,
                f"{path}[{index}]",
                errors,
                inherited_local_dev=inherited_local_dev,
            )


def _validate_status_fields(obj: Any, path: str, errors: list[str]) -> None:
    if isinstance(obj, dict):
        if "check_id" not in obj:
            status = obj.get("status")
            if isinstance(status, str):
                if "certificate_id" in obj:
                    if status not in TRACE_CERTIFICATE_STATUSES:
                        errors.append(f"{path}: invalid TraceCertificate status {status!r}")
                elif status not in ARTIFACT_STATUSES:
                    errors.append(f"{path}: unknown status {status!r}")
        for key, value in obj.items():
            child = f"{path}.{key}" if path else key
            _validate_status_fields(value, child, errors)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _validate_status_fields(item, f"{path}[{index}]", errors)


def _validate_science_claim_bundle(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    assumption_set = data.get("assumption_set")
    if not isinstance(assumption_set, dict):
        errors.append("ScienceClaimBundle.v0 requires assumption_set")
    else:
        assumptions = assumption_set.get("assumptions")
        if not assumptions:
            errors.append("ScienceClaimBundle.v0 requires non-empty assumption_set.assumptions")

    receipts = data.get("runtime_receipts")
    if not isinstance(receipts, list) or len(receipts) == 0:
        errors.append("ScienceClaimBundle.v0 requires non-empty runtime_receipts")

    claim = data.get("claim_artifact")
    if isinstance(claim, dict):
        ref = claim.get("assumption_set_ref")
        if not ref or not str(ref).strip():
            errors.append("claim_artifact requires non-empty assumption_set_ref")
        elif isinstance(assumption_set, dict):
            if ref != assumption_set.get("assumption_set_id"):
                errors.append(
                    "claim_artifact.assumption_set_ref must match assumption_set.assumption_set_id"
                )

    certificates = data.get("certificates")
    if not isinstance(certificates, list):
        certificates = []

    claim_status = str(claim.get("status") or "") if isinstance(claim, dict) else ""
    if claim_status in CERTIFIED_CLAIM_STATUSES and len(certificates) == 0:
        errors.append("certified ScienceClaimBundle requires at least one TraceCertificate")

    if isinstance(receipts, list):
        for receipt in receipts:
            if not isinstance(receipt, dict):
                continue
            r_hash = receipt.get("trace_hash")
            for cert in certificates:
                if not isinstance(cert, dict):
                    continue
                c_status = str(cert.get("status") or "")
                if c_status and c_status not in TRACE_CERTIFICATE_STATUSES:
                    errors.append(
                        f"TraceCertificate {cert.get('certificate_id')}: "
                        f"invalid status {c_status!r}"
                    )
                c_hash = cert.get("trace_hash")
                if r_hash and c_hash and r_hash != c_hash:
                    errors.append(
                        f"trace_hash mismatch: receipt {receipt.get('receipt_id')} "
                        f"({r_hash}) vs certificate {cert.get('certificate_id')} ({c_hash})"
                    )

    return errors


def _validate_verification_result(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    checks = data.get("checks")
    if not isinstance(checks, list):
        return errors
    has_failed = any(
        isinstance(check, dict) and check.get("status") == "failed" for check in checks
    )
    top_status = str(data.get("status") or "")
    if has_failed and top_status in IMPORT_READY_VERIFICATION_STATUSES:
        errors.append(
            "VerificationResult.v0 with failed checks cannot use import-ready status "
            f"{top_status!r} (Scientific Memory import contract)"
        )
    return errors


def _validate_signed_bundle(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scb = data.get("science_claim_bundle")
    if isinstance(scb, dict):
        errors.extend(_validate_science_claim_bundle(scb))
    vr = data.get("verification_result")
    if isinstance(vr, dict):
        _validate_status_fields(vr, "verification_result", errors)
        errors.extend(_validate_verification_result(vr))
    return errors


def _validate_pfcore_claim_class(data: dict[str, Any], path: str, errors: list[str]) -> None:
    claim_class = data.get("claim_class")
    if not isinstance(claim_class, str):
        return
    if claim_class not in PF_CORE_CLAIM_CLASSES:
        errors.append(f"{path}: invalid claim_class {claim_class!r}")
        return
    if claim_class == "LeanKernelChecked" and not data.get("proof_ref"):
        errors.append(
            f"{path}: claim_class LeanKernelChecked requires proof_ref (ClaimClassOverclaim)"
        )
    if claim_class == "LeanKernelChecked" and not data.get("proof_term_ref"):
        errors.append(
            f"{path}: claim_class LeanKernelChecked requires proof_term_ref (ClaimClassOverclaim)"
        )
    if claim_class == "LeanKernelChecked" and data.get("lean_proof_checked") is not True:
        errors.append(
            f"{path}: claim_class LeanKernelChecked requires lean_proof_checked=true"
        )


def _validate_pfcore_trace(data: dict[str, Any]) -> list[str]:
    from pcs_core.pf_core_runtime import validate_pfcore_trace_hash_chain

    errors: list[str] = []
    _validate_pfcore_claim_class(data, "root", errors)
    errors.extend(validate_pfcore_trace_hash_chain(data))
    return errors


def _validate_pfcore_certificate(data: dict[str, Any]) -> list[str]:
    from pcs_core.lean_catalog import PF_CORE_CONCRETE_PROOF_THEOREMS
    from pcs_core.registry_data import enforce_assumption_declared, registry_entries

    errors: list[str] = []
    _validate_pfcore_claim_class(data, "root", errors)
    claim_class = data.get("claim_class")
    lean_proof_checked = data.get("lean_proof_checked") is True
    if lean_proof_checked and not data.get("proof_term_ref"):
        errors.append("root: lean_proof_checked requires proof_term_ref")
    if lean_proof_checked:
        build = data.get("lean_build_status")
        if not isinstance(build, dict) or build.get("ok") is not True:
            errors.append("root: lean_proof_checked requires lean_build_status.ok=true")
        theorems = data.get("theorems_checked")
        if isinstance(theorems, list):
            theorem_set = {str(item) for item in theorems}
            missing = PF_CORE_CONCRETE_PROOF_THEOREMS - theorem_set
            if missing:
                errors.append(
                    "root: lean_proof_checked theorems_checked missing "
                    f"{sorted(missing)!r}"
                )
        obligations = data.get("obligations")
        if isinstance(obligations, list):
            required = {
                "concrete_trace_safe",
                "concrete_trace_safe_prop",
                "concrete_allowed_events_allowed",
            }
            passed = {
                str(item.get("theorem"))
                for item in obligations
                if isinstance(item, dict) and item.get("passed") is True
            }
            missing_obligations = required - passed
            if missing_obligations:
                errors.append(
                    "root: lean_proof_checked obligations missing passed proofs for "
                    f"{sorted(missing_obligations)!r}"
                )
    if claim_class == "LeanKernelChecked" and not lean_proof_checked:
        errors.append("root: claim_class LeanKernelChecked requires lean_proof_checked=true")
    if claim_class == "LeanKernelChecked":
        env_hash = data.get("lean_environment_hash")
        if not isinstance(env_hash, str) or not env_hash.startswith("sha256:"):
            errors.append("root: claim_class LeanKernelChecked requires lean_environment_hash")
    errors.extend(enforce_assumption_declared(data, registry_entries().get("PFCoreCertificate.v0")))
    return errors


def _validate_lean_check_result(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    claim_class = data.get("claim_class")
    if isinstance(claim_class, str) and claim_class not in PF_CORE_CLAIM_CLASSES:
        errors.append(f"root: invalid claim_class {claim_class!r}")
    status = str(data.get("status") or "")
    lean_proof_checked = data.get("lean_proof_checked") is True
    if status == "LeanProofChecked" and claim_class != "LeanKernelChecked":
        errors.append("root: status LeanProofChecked requires claim_class LeanKernelChecked")
    if status == "ReplayValidated" and claim_class != "ReplayValidated":
        errors.append("root: status ReplayValidated requires claim_class ReplayValidated")
    if status == "LeanProofChecked" and not lean_proof_checked:
        errors.append("root: status LeanProofChecked requires lean_proof_checked=true")
    if claim_class == "LeanKernelChecked" and status != "LeanProofChecked":
        errors.append("root: claim_class LeanKernelChecked requires status LeanProofChecked")
    cert = data.get("certificate")
    if isinstance(cert, dict):
        errors.extend(_validate_pfcore_certificate(cert))
    return errors
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
        _validate_pfcore_claim_class(data, "root", errors)

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


def iter_pf_core_example_dirs(kind: str) -> list[Path]:
    root = repo_root() / "examples" / f"pf-core-{kind}"
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def load_pf_core_fixture_manifest(case_dir: Path) -> dict[str, Any]:
    manifest_path = case_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValidationError(f"Missing manifest.json in {case_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValidationError(f"manifest.json root must be an object in {case_dir}")
    return manifest


def check_pf_core_valid_fixtures() -> None:
    from pcs_core.pf_core_replay import replay_trace

    for case_dir in iter_pf_core_example_dirs("valid"):
        manifest = None
        manifest_path = case_dir / "manifest.json"
        if manifest_path.is_file():
            manifest = load_pf_core_fixture_manifest(case_dir)
        for path in sorted(case_dir.glob("*.json")):
            if path.name == "manifest.json":
                continue
            if path.name == "tool_use_trace.json" and (case_dir / "pfcore_trace.json").is_file():
                continue
            validate_file(path)
        if manifest and manifest.get("replay_required"):
            trace_path = case_dir / str(manifest.get("trace_file") or "trace.json")
            if trace_path.is_file():
                result = replay_trace(trace_path)
                if not result.match:
                    raise ValidationError(
                        f"Replay failed for {case_dir}: {result.diffs!r}"
                    )


def check_pf_core_invalid_fixtures() -> None:
    from pcs_core.pf_core_contract import validate_trace_contracts
    from pcs_core.pf_core_runtime import (
        DroppedDeniedEvent,
        HandoffAuthorityExpansion,
        MissingPrincipal,
        UnknownCapability,
        UnknownEffect,
        compile_runtime_observation_to_event,
        compile_tool_use_trace_to_pfcore_trace,
        validate_denied_events_preserved,
        validate_handoff_authority,
        validate_pfcore_trace_hash_chain,
    )

    for case_dir in iter_pf_core_example_dirs("invalid"):
        manifest = load_pf_core_fixture_manifest(case_dir)
        expected_error = str(manifest["expected_error"])
        must_fail_at = str(manifest["must_fail_at"])

        if must_fail_at == "runtime_to_pfcore_event":
            observation = json.loads((case_dir / "observation.json").read_text(encoding="utf-8"))
            try:
                compile_runtime_observation_to_event(observation)
            except (UnknownCapability, UnknownEffect, MissingPrincipal) as exc:
                if exc.code != expected_error:
                    raise ValidationError(
                        f"{case_dir}: expected {expected_error!r}, got {exc.code!r}"
                    ) from exc
            else:
                raise ValidationError(f"Expected {case_dir} to fail at {must_fail_at}")
            continue

        if must_fail_at == "validate_pfcore_trace_hash_chain":
            trace = json.loads((case_dir / "trace.json").read_text(encoding="utf-8"))
            errors = validate_pfcore_trace_hash_chain(trace)
            if not any(expected_error in err for err in errors):
                raise ValidationError(
                    f"Expected {case_dir} to fail with {expected_error!r}, got {errors!r}"
                )
            continue

        if must_fail_at == "validate_denied_events_preserved":
            tool_use_trace = json.loads(
                (case_dir / "tool_use_trace.json").read_text(encoding="utf-8")
            )
            pfcore_trace = json.loads((case_dir / "pfcore_trace.json").read_text(encoding="utf-8"))
            try:
                validate_denied_events_preserved(tool_use_trace, pfcore_trace)
            except DroppedDeniedEvent as exc:
                if exc.code != expected_error:
                    raise ValidationError(
                        f"{case_dir}: expected {expected_error!r}, got {exc.code!r}"
                    ) from exc
            else:
                raise ValidationError(f"Expected {case_dir} to fail at {must_fail_at}")
            continue

        if must_fail_at == "validate_handoff_authority":
            handoff = json.loads((case_dir / "handoff.json").read_text(encoding="utf-8"))
            try:
                validate_handoff_authority(handoff)
            except HandoffAuthorityExpansion as exc:
                if exc.code != expected_error:
                    raise ValidationError(
                        f"{case_dir}: expected {expected_error!r}, got {exc.code!r}"
                    ) from exc
            else:
                raise ValidationError(f"Expected {case_dir} to fail at {must_fail_at}")
            continue

        if must_fail_at == "compile_tool_use_trace_to_pfcore_trace":
            tool_use_trace = json.loads(
                (case_dir / "tool_use_trace.json").read_text(encoding="utf-8")
            )
            try:
                compile_tool_use_trace_to_pfcore_trace(tool_use_trace)
            except HandoffAuthorityExpansion as exc:
                if exc.code != expected_error:
                    raise ValidationError(
                        f"{case_dir}: expected {expected_error!r}, got {exc.code!r}"
                    ) from exc
            else:
                raise ValidationError(f"Expected {case_dir} to fail at {must_fail_at}")
            continue

        if must_fail_at == "validate_trace_contracts":
            trace = json.loads((case_dir / "trace.json").read_text(encoding="utf-8"))
            contracts_dir = case_dir / "contracts"
            contracts = {
                str(data["contract_id"]): data
                for data in (
                    json.loads(path.read_text(encoding="utf-8"))
                    for path in sorted(contracts_dir.glob("*.json"))
                )
            }
            issues = validate_trace_contracts(trace, contracts)
            if not any(issue.code == expected_error for issue in issues):
                raise ValidationError(
                    f"Expected {case_dir} to fail with {expected_error!r}, got "
                    f"{[issue.code for issue in issues]!r}"
                )
            continue

        if must_fail_at == "validate_tenant_isolation":
            from pcs_core.pf_core_runtime import validate_tenant_isolation

            trace = json.loads((case_dir / "trace.json").read_text(encoding="utf-8"))
            errors = validate_tenant_isolation(trace)
            if not any(expected_error in err for err in errors):
                raise ValidationError(
                    f"Expected {case_dir} to fail with {expected_error!r}, got {errors!r}"
                )
            continue

        raise ValidationError(f"Unknown must_fail_at {must_fail_at!r} in {case_dir}")



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
