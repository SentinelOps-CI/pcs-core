"""Artifact type detection and JSON Schema validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from pcs_core.paths import schemas_dir

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


class ValidationError(Exception):
    """Raised when artifact validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


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
