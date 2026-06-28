"""Canonical PCS v0.1 artifact registry entries (protocol authority)."""

from __future__ import annotations

from typing import Any

PCS_CORE = "pcs-core"
LABTRUST = "LabTrust-Gym"
CERTIFYEDGE = "CertifyEdge"
PF = "Provability Fabric"
SM = "Scientific Memory"
AGENT_RUNTIME = "AgentRuntime"
AGENT_TOOL_USE_DEMO = "agent-tool-use demo producer"
SCIENTIFIC_COMPUTATION_DEMO = "scientific-computation demo producer"

_HANDOFF_PRODUCERS = [LABTRUST, CERTIFYEDGE, PF, SM]


def _sc(check_id: str, severity: str, responsible_component: str) -> dict[str, Any]:
    if severity in {"optional", "warning_only"}:
        execution_required, allowed_to_skip = False, True
    else:
        execution_required, allowed_to_skip = True, False
    return {
        "check_id": check_id,
        "severity": severity,
        "responsible_component": responsible_component,
        "execution_required_in_release_mode": execution_required,
        "allowed_to_skip": allowed_to_skip,
    }


def _entry(
    *,
    artifact_type: str,
    schema: str,
    schema_owner: str,
    runtime_producer: str,
    allowed_runtime_producers: list[str],
    allowed_statuses: list[str],
    required_release_fields: list[str],
    semantic_checks: list[dict[str, str]],
    consumer_repos: list[str] | None = None,
    canonical_hash_required: bool = True,
    release_mode_required: bool = True,
) -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "schema": schema,
        "schema_owner": schema_owner,
        "runtime_producer": runtime_producer,
        "allowed_runtime_producers": allowed_runtime_producers,
        "producer": runtime_producer,
        "allowed_statuses": allowed_statuses,
        "required_release_fields": required_release_fields,
        "semantic_checks": semantic_checks,
        "consumer_repos": consumer_repos or [runtime_producer],
        "canonical_hash_required": canonical_hash_required,
        "release_mode_required": release_mode_required,
    }


_PF_CORE_PRIMITIVE_CHECKS = [
    {
        "check_id": "explicit_artifact_type",
        "severity": "release_blocking",
        "responsible_component": PCS_CORE,
        "execution_required_in_release_mode": True,
        "allowed_to_skip": False,
    },
    {
        "check_id": "schema_valid",
        "severity": "release_blocking",
        "responsible_component": PCS_CORE,
        "execution_required_in_release_mode": True,
        "allowed_to_skip": False,
    },
]

_PF_CORE_ARTIFACT_TYPES = frozenset(
    {
        "PFCorePrincipal.v0",
        "PFCoreCapability.v0",
        "PFCoreResource.v0",
        "PFCoreAction.v0",
        "PFCoreEvent.v0",
        "PFCoreTrace.v0",
        "PFCoreContract.v0",
        "PFCoreHandoff.v0",
        "PFCoreCertificate.v0",
        "PFCoreRuntimeObservation.v0",
    }
)


def _pf_core_primitive_entry(
    artifact_type: str,
    *,
    runtime_producer: str = PCS_CORE,
    allowed_runtime_producers: list[str] | None = None,
) -> dict[str, Any]:
    producers = allowed_runtime_producers or [PCS_CORE, AGENT_RUNTIME]
    return _entry(
        artifact_type=artifact_type,
        schema=f"schemas/{artifact_type}.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=runtime_producer,
        allowed_runtime_producers=producers,
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "artifact_type",
            "signature_or_digest",
        ],
        semantic_checks=list(_PF_CORE_PRIMITIVE_CHECKS),
        consumer_repos=[PCS_CORE, AGENT_RUNTIME],
        release_mode_required=False,
    )


def _pf_core_release_entry(
    artifact_type: str,
    *,
    id_field: str,
    runtime_producer: str = PCS_CORE,
    extra_release_fields: list[str] | None = None,
) -> dict[str, Any]:
    required = [
        "schema_version",
        "artifact_type",
        id_field,
        "claim_class",
        "source_repo",
        "source_commit",
        "signature_or_digest",
    ]
    if extra_release_fields:
        required.extend(extra_release_fields)
    return _entry(
        artifact_type=artifact_type,
        schema=f"schemas/{artifact_type}.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=runtime_producer,
        allowed_runtime_producers=[PCS_CORE, AGENT_RUNTIME],
        allowed_statuses=[
            "Draft",
            "RuntimeChecked",
            "CertificateChecked",
            "LeanKernelChecked",
            "Rejected",
            "Stale",
        ],
        required_release_fields=required,
        semantic_checks=[
            *_PF_CORE_PRIMITIVE_CHECKS,
            {
                "check_id": "claim_class_matches_assurance",
                "severity": "release_blocking",
                "responsible_component": PCS_CORE,
                "execution_required_in_release_mode": True,
                "allowed_to_skip": False,
            },
            {
                "check_id": "lean_kernel_proof",
                "severity": "release_blocking",
                "responsible_component": PCS_CORE,
                "execution_required_in_release_mode": True,
                "allowed_to_skip": False,
            },
            {
                "check_id": "lean_library_build",
                "severity": "release_blocking",
                "responsible_component": PCS_CORE,
                "execution_required_in_release_mode": True,
                "allowed_to_skip": False,
            },
        ],
        consumer_repos=[PCS_CORE, AGENT_RUNTIME],
        release_mode_required=True,
    )


_REGISTRY_ENTRIES: dict[str, dict[str, Any]] = {
    "AssumptionSet.v0": _entry(
        artifact_type="AssumptionSet.v0",
        schema="schemas/AssumptionSet.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=LABTRUST,
        allowed_runtime_producers=[LABTRUST],
        allowed_statuses=["Draft", "HumanReviewed", "RuntimeObserved", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "assumption_set_id",
            "status",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("source_commit_not_placeholder", "release_blocking", LABTRUST),
        ],
        consumer_repos=[LABTRUST],
    ),
    "SourceSpan.v0": _entry(
        artifact_type="SourceSpan.v0",
        schema="schemas/SourceSpan.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=LABTRUST,
        allowed_runtime_producers=[LABTRUST],
        allowed_statuses=["Draft", "Extracted", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "source_span_id",
            "status",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("source_commit_not_placeholder", "release_blocking", LABTRUST),
        ],
        consumer_repos=[LABTRUST],
    ),
    "ClaimArtifact.v0": _entry(
        artifact_type="ClaimArtifact.v0",
        schema="schemas/ClaimArtifact.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=LABTRUST,
        allowed_runtime_producers=[LABTRUST],
        allowed_statuses=[
            "Draft",
            "RuntimeObserved",
            "CertificateChecked",
            "ProofChecked",
            "Rejected",
            "Stale",
        ],
        required_release_fields=[
            "schema_version",
            "artifact_id",
            "assumption_set_ref",
            "status",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("assumption_set_ref_present", "release_blocking", LABTRUST),
        ],
        consumer_repos=[LABTRUST, CERTIFYEDGE],
    ),
    "RuntimeReceipt.v0": _entry(
        artifact_type="RuntimeReceipt.v0",
        schema="schemas/RuntimeReceipt.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=LABTRUST,
        allowed_runtime_producers=[LABTRUST],
        allowed_statuses=["RuntimeObserved", "RuntimeChecked", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "receipt_id",
            "trace_hash",
            "status",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("trace_hash_present", "release_blocking", LABTRUST),
            _sc("source_commit_matches_release_manifest", "release_blocking", LABTRUST),
        ],
        consumer_repos=[LABTRUST, CERTIFYEDGE, PF],
    ),
    "TraceCertificate.v0": _entry(
        artifact_type="TraceCertificate.v0",
        schema="schemas/TraceCertificate.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=CERTIFYEDGE,
        allowed_runtime_producers=[CERTIFYEDGE],
        allowed_statuses=["CertificatePending", "CertificateChecked", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "certificate_id",
            "trace_hash",
            "spec_hash",
            "status",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("trace_hash_matches_runtime_receipt", "release_blocking", CERTIFYEDGE),
            _sc("status_is_certificate_checked_for_release", "release_blocking", CERTIFYEDGE),
            _sc("source_commit_matches_release_manifest", "release_blocking", CERTIFYEDGE),
        ],
        consumer_repos=[CERTIFYEDGE, LABTRUST, PF, SM],
    ),
    "EvidenceBundle.v0": _entry(
        artifact_type="EvidenceBundle.v0",
        schema="schemas/EvidenceBundle.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=LABTRUST,
        allowed_runtime_producers=[LABTRUST],
        allowed_statuses=["Draft", "CertificateChecked", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "bundle_id",
            "status",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("certificate_refs_resolve", "producer_responsible", LABTRUST),
        ],
        consumer_repos=[LABTRUST, CERTIFYEDGE],
    ),
    "ScienceClaimBundle.v0": _entry(
        artifact_type="ScienceClaimBundle.v0",
        schema="schemas/ScienceClaimBundle.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=LABTRUST,
        allowed_runtime_producers=[LABTRUST],
        allowed_statuses=[
            "Draft",
            "RuntimeObserved",
            "CertificateChecked",
            "ProofChecked",
            "Rejected",
            "Stale",
        ],
        required_release_fields=[
            "schema_version",
            "bundle_id",
            "assumption_set",
            "runtime_receipts",
            "status",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("non_empty_runtime_receipts", "release_blocking", LABTRUST),
            _sc(
                "certified_bundle_has_certificate_when_checked",
                "release_blocking",
                LABTRUST,
            ),
        ],
        consumer_repos=[LABTRUST, PF, SM],
    ),
    "VerificationResult.v0": _entry(
        artifact_type="VerificationResult.v0",
        schema="schemas/VerificationResult.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PF,
        allowed_runtime_producers=[PF],
        allowed_statuses=["ProofChecked", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "verification_id",
            "status",
            "verified_input",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc(
                "verified_input_bundle_hash_matches_certified",
                "release_blocking",
                PF,
            ),
            _sc(
                "failed_checks_block_import_ready_status",
                "release_blocking",
                PF,
            ),
        ],
        consumer_repos=[PF, SM],
    ),
    "SignedScienceClaimBundle.v0": _entry(
        artifact_type="SignedScienceClaimBundle.v0",
        schema="schemas/SignedScienceClaimBundle.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PF,
        allowed_runtime_producers=[PF],
        allowed_statuses=["ProofChecked", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "signed_bundle_id",
            "signed_input_bundle_hash",
            "science_claim_bundle",
            "verification_result",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc(
                "signed_input_bundle_hash_matches_certified",
                "release_blocking",
                PF,
            ),
            _sc(
                "embedded_bundle_passes_science_claim_semantics",
                "producer_responsible",
                PF,
            ),
        ],
        consumer_repos=[PF, SM],
    ),
    "ReleaseManifest.v0": _entry(
        artifact_type="ReleaseManifest.v0",
        schema="schemas/ReleaseManifest.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Rejected", "Stale", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "release_id",
            "release_candidate",
            "validation_profile",
            "producer_repos",
            "artifacts",
            "release_status",
            "chain_root",
            "release_chain_validation_result",
            "canonical_signed_bundle",
            "canonical_claim_id",
            "limitations_notice",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("release_mode_commit_policy", "release_blocking", PCS_CORE),
            _sc("artifact_hashes_match_files", "release_blocking", PCS_CORE),
        ],
        consumer_repos=[PCS_CORE, LABTRUST, CERTIFYEDGE, PF, SM],
    ),
    "HandoffManifest.v0": _entry(
        artifact_type="HandoffManifest.v0",
        schema="schemas/HandoffManifest.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=LABTRUST,
        allowed_runtime_producers=_HANDOFF_PRODUCERS,
        allowed_statuses=["Draft", "Validated", "Rejected", "Stale", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "handoff_id",
            "handoff_kind",
            "input_artifacts",
            "expected_outputs",
            "invariants",
            "status",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("handoff_input_hashes_when_validated", "release_blocking", PCS_CORE),
        ],
        consumer_repos=_HANDOFF_PRODUCERS,
    ),
    "ComponentReleaseFragment.v0": _entry(
        artifact_type="ComponentReleaseFragment.v0",
        schema="schemas/ComponentReleaseFragment.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=LABTRUST,
        allowed_runtime_producers=[LABTRUST, CERTIFYEDGE, PF, SM],
        allowed_statuses=["Draft", "Validated", "Rejected", "Stale", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "component",
            "source_repo",
            "source_commit",
            "artifacts",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("component_artifacts_match_release_pins", "release_blocking", PCS_CORE),
        ],
        consumer_repos=[LABTRUST, PCS_CORE],
    ),
    "ReleaseChainValidationResult.v0": _entry(
        artifact_type="ReleaseChainValidationResult.v0",
        schema="schemas/ReleaseChainValidationResult.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["ProofChecked", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "validation_id",
            "release_id",
            "status",
            "checks",
            "artifacts_checked",
            "failure_codes",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("status_matches_check_outcomes", "validator_responsible", PCS_CORE),
        ],
        consumer_repos=[PCS_CORE, SM],
    ),
    "ToolUseTrace.v0": _entry(
        artifact_type="ToolUseTrace.v0",
        schema="schemas/ToolUseTrace.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=AGENT_TOOL_USE_DEMO,
        allowed_runtime_producers=[AGENT_TOOL_USE_DEMO],
        allowed_statuses=["Draft", "RuntimeObserved", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "trace_id",
            "workflow_id",
            "agent_id",
            "policy_id",
            "policy_hash",
            "started_at",
            "completed_at",
            "tool_calls",
            "trace_hash",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("trace_hash_present", "release_blocking", AGENT_TOOL_USE_DEMO),
            _sc("no_unknown_authorization_status", "release_blocking", AGENT_TOOL_USE_DEMO),
        ],
        consumer_repos=[CERTIFYEDGE, PF, SM, PCS_CORE],
        release_mode_required=True,
    ),
    "ToolUseCertificate.v0": _entry(
        artifact_type="ToolUseCertificate.v0",
        schema="schemas/ToolUseCertificate.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=CERTIFYEDGE,
        allowed_runtime_producers=[CERTIFYEDGE],
        allowed_statuses=["CertificateChecked", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "certificate_id",
            "trace_hash",
            "policy_hash",
            "property_id",
            "checker",
            "checker_version",
            "status",
            "violations",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("tool_trace_hash_matches_certificate", "release_blocking", CERTIFYEDGE),
            _sc("policy_hash_matches_certificate", "release_blocking", CERTIFYEDGE),
            _sc("certificate_status_checked_for_release", "release_blocking", CERTIFYEDGE),
            _sc("no_unauthorized_tool_calls", "release_blocking", CERTIFYEDGE),
            _sc("source_commit_matches_release_manifest", "release_blocking", CERTIFYEDGE),
            _sc("signature_or_digest_valid", "release_blocking", CERTIFYEDGE),
        ],
        consumer_repos=[PF, SM, PCS_CORE],
        release_mode_required=True,
    ),
    "WorkflowProfile.v0": _entry(
        artifact_type="WorkflowProfile.v0",
        schema="schemas/WorkflowProfile.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "workflow_id",
            "domain",
            "description",
            "runtime_artifacts",
            "certificate_artifacts",
            "handoff_sequence",
            "required_registry_entries",
            "required_admission_profile",
            "status_policy",
            "failure_modes",
            "limitations_notice",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("required_registry_entries_registered", "required", PCS_CORE),
        ],
        consumer_repos=[PCS_CORE, LABTRUST, CERTIFYEDGE, PF, SM, AGENT_RUNTIME],
        release_mode_required=False,
    ),
    "DatasetReceipt.v0": _entry(
        artifact_type="DatasetReceipt.v0",
        schema="schemas/DatasetReceipt.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=SCIENTIFIC_COMPUTATION_DEMO,
        allowed_runtime_producers=[SCIENTIFIC_COMPUTATION_DEMO],
        allowed_statuses=["Draft", "RuntimeObserved", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "dataset_id",
            "dataset_name",
            "dataset_version",
            "files",
            "aggregate_hash",
            "source_uri",
            "source_repo",
            "source_commit",
            "license",
            "created_at",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("source_commit_not_placeholder", "release_blocking", SCIENTIFIC_COMPUTATION_DEMO),
            _sc("signature_or_digest_valid", "release_blocking", SCIENTIFIC_COMPUTATION_DEMO),
        ],
        consumer_repos=[CERTIFYEDGE, PF, SM, PCS_CORE],
        release_mode_required=True,
    ),
    "EnvironmentReceipt.v0": _entry(
        artifact_type="EnvironmentReceipt.v0",
        schema="schemas/EnvironmentReceipt.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=SCIENTIFIC_COMPUTATION_DEMO,
        allowed_runtime_producers=[SCIENTIFIC_COMPUTATION_DEMO],
        allowed_statuses=["Draft", "RuntimeObserved", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "environment_id",
            "environment_kind",
            "os",
            "architecture",
            "language_runtimes",
            "packages",
            "container_image",
            "container_digest",
            "hardware_summary",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("source_commit_not_placeholder", "release_blocking", SCIENTIFIC_COMPUTATION_DEMO),
            _sc("signature_or_digest_valid", "release_blocking", SCIENTIFIC_COMPUTATION_DEMO),
        ],
        consumer_repos=[CERTIFYEDGE, PF, SM, PCS_CORE],
        release_mode_required=True,
    ),
    "ComputationRunReceipt.v0": _entry(
        artifact_type="ComputationRunReceipt.v0",
        schema="schemas/ComputationRunReceipt.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=SCIENTIFIC_COMPUTATION_DEMO,
        allowed_runtime_producers=[SCIENTIFIC_COMPUTATION_DEMO],
        allowed_statuses=["Draft", "RuntimeObserved", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "run_id",
            "workflow_id",
            "command",
            "code_repo",
            "code_commit",
            "dataset_receipt_ref",
            "environment_receipt_ref",
            "started_at",
            "completed_at",
            "exit_code",
            "stdout_hash",
            "stderr_hash",
            "result_artifact_refs",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("source_commit_not_placeholder", "release_blocking", SCIENTIFIC_COMPUTATION_DEMO),
            _sc("signature_or_digest_valid", "release_blocking", SCIENTIFIC_COMPUTATION_DEMO),
        ],
        consumer_repos=[CERTIFYEDGE, PF, SM, PCS_CORE],
        release_mode_required=True,
    ),
    "ResultArtifact.v0": _entry(
        artifact_type="ResultArtifact.v0",
        schema="schemas/ResultArtifact.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=SCIENTIFIC_COMPUTATION_DEMO,
        allowed_runtime_producers=[SCIENTIFIC_COMPUTATION_DEMO],
        allowed_statuses=["Draft", "RuntimeObserved", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "result_id",
            "result_kind",
            "path",
            "sha256",
            "size_bytes",
            "media_type",
            "description",
            "produced_by_run",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("source_commit_not_placeholder", "release_blocking", SCIENTIFIC_COMPUTATION_DEMO),
            _sc("signature_or_digest_valid", "release_blocking", SCIENTIFIC_COMPUTATION_DEMO),
        ],
        consumer_repos=[CERTIFYEDGE, PF, SM, PCS_CORE],
        release_mode_required=True,
    ),
    "ComputationWitness.v0": _entry(
        artifact_type="ComputationWitness.v0",
        schema="schemas/ComputationWitness.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=CERTIFYEDGE,
        allowed_runtime_producers=[CERTIFYEDGE],
        allowed_statuses=["CertificateChecked", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "witness_id",
            "workflow_id",
            "dataset_hash",
            "environment_hash",
            "run_receipt_hash",
            "result_hashes",
            "code_repo",
            "code_commit",
            "checker",
            "checker_version",
            "status",
            "violations",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("dataset_hash_matches_receipt", "release_blocking", CERTIFYEDGE),
            _sc("environment_hash_matches_receipt", "release_blocking", CERTIFYEDGE),
            _sc("run_receipt_hash_matches_declared_run", "release_blocking", CERTIFYEDGE),
            _sc("result_hashes_match_result_artifacts", "release_blocking", CERTIFYEDGE),
            _sc("code_commit_present", "release_blocking", CERTIFYEDGE),
            _sc("computation_status_checked_for_release", "release_blocking", CERTIFYEDGE),
            _sc("source_commit_matches_release_manifest", "release_blocking", CERTIFYEDGE),
            _sc("signature_or_digest_valid", "release_blocking", CERTIFYEDGE),
        ],
        consumer_repos=[PF, SM, PCS_CORE],
        release_mode_required=True,
    ),
    "ProofObligation.v0": _entry(
        artifact_type="ProofObligation.v0",
        schema="schemas/ProofObligation.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "obligation_id",
            "release_id",
            "workflow_id",
            "obligations",
            "source_artifacts",
            "lean_module",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("obligations_reference_known_kinds", "required", PCS_CORE),
        ],
        consumer_repos=[PCS_CORE, LABTRUST, CERTIFYEDGE, PF, SM],
        release_mode_required=False,
    ),
    "LeanCheckResult.v0": _entry(
        artifact_type="LeanCheckResult.v0",
        schema="schemas/LeanCheckResult.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["ProofChecked", "Rejected", "Stale"],
        required_release_fields=[
            "schema_version",
            "check_id",
            "proof_obligation_id",
            "lean_module",
            "lean_theorem",
            "status",
            "checked_at",
            "lean_version",
            "source_repo",
            "source_commit",
            "failure_reason",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("obligation_results_match_proof_obligation", "release_blocking", PCS_CORE),
            _sc("lean_theorem_in_catalog", "required", PCS_CORE),
        ],
        consumer_repos=[PCS_CORE],
        release_mode_required=False,
    ),
    "BenchmarkMetricRegistry.v0": _entry(
        artifact_type="BenchmarkMetricRegistry.v0",
        schema="schemas/BenchmarkMetricRegistry.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "registry_id",
            "registry_version",
            "metrics",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE],
        release_mode_required=False,
    ),
    "ExplainQualityReport.v0": _entry(
        artifact_type="ExplainQualityReport.v0",
        schema="schemas/ExplainQualityReport.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE, PF],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "report_id",
            "suite_id",
            "case_id",
            "producer_id",
            "required_sections",
            "sections",
            "sections_present_count",
            "sections_required_count",
            "quality_score",
            "gaps",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE, PF, SM],
        release_mode_required=False,
    ),
    "ProfileCoverageReport.v0": _entry(
        artifact_type="ProfileCoverageReport.v0",
        schema="schemas/ProfileCoverageReport.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE, PF],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "coverage_id",
            "workflow_profile_id",
            "producer_id",
            "artifact_types_required",
            "artifact_types_covered",
            "semantic_checks_required",
            "semantic_checks_covered",
            "handoff_steps_required",
            "handoff_steps_covered",
            "numerator",
            "denominator",
            "coverage_ratio",
            "details",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE, PF],
        release_mode_required=False,
    ),
    "BenchmarkRegistry.v0": _entry(
        artifact_type="BenchmarkRegistry.v0",
        schema="schemas/BenchmarkRegistry.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "registry_id",
            "registry_version",
            "suites",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE],
        release_mode_required=False,
    ),
    "BenchmarkTask.v0": _entry(
        artifact_type="BenchmarkTask.v0",
        schema="schemas/BenchmarkTask.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "task_id",
            "workflow_id",
            "domain",
            "description",
            "input_case_set",
            "expected_outputs",
            "metrics",
            "success_criteria",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE],
        release_mode_required=False,
    ),
    "BenchmarkCase.v0": _entry(
        artifact_type="BenchmarkCase.v0",
        schema="schemas/BenchmarkCase.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "case_id",
            "task_id",
            "workflow_id",
            "case_kind",
            "input_artifacts",
            "expected_status",
            "expected_system_outcome",
            "expected_failure_code",
            "expected_responsible_component",
            "expected_repair_hint_kind",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE],
        release_mode_required=False,
    ),
    "BenchmarkRun.v0": _entry(
        artifact_type="BenchmarkRun.v0",
        schema="schemas/BenchmarkRun.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "run_id",
            "task_id",
            "case_id",
            "started_at",
            "completed_at",
            "commands",
            "artifacts_produced",
            "observed_status",
            "observed_failure_code",
            "observed_responsible_component",
            "observed_repair_hint",
            "duration_ms",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE],
        release_mode_required=False,
    ),
    "BenchmarkReport.v0": _entry(
        artifact_type="BenchmarkReport.v0",
        schema="schemas/BenchmarkReport.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "report_id",
            "benchmark_suite_id",
            "runs",
            "metrics",
            "metric_summaries",
            "summary",
            "coverage",
            "failures",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE],
        release_mode_required=False,
    ),
    "BenchmarkArtifactRef.v0": _entry(
        artifact_type="BenchmarkArtifactRef.v0",
        schema="schemas/BenchmarkArtifactRef.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[
            PCS_CORE,
            "pcs-bench",
            "labtrust-gym",
            "certifyedge",
            "provability-fabric",
            "scientific-memory",
        ],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "artifact_type",
            "path",
            "sha256",
            "role",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE, "pcs-bench"],
        release_mode_required=False,
    ),
    "PcsBenchIngest.v0": _entry(
        artifact_type="PcsBenchIngest.v0",
        schema="schemas/PcsBenchIngest.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[
            PCS_CORE,
            "pcs-bench",
            "labtrust-gym",
            "certifyedge",
            "provability-fabric",
            "scientific-memory",
        ],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "producer_id",
            "suite_id",
            "workflow_id",
            "benchmark_runs",
            "coverage_reports",
            "failure_localization_reports",
            "explain_quality_reports",
            "profile_coverage_reports",
            "commands",
            "logs",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE, "pcs-bench"],
        release_mode_required=False,
    ),
    "MetricSummary.v0": _entry(
        artifact_type="MetricSummary.v0",
        schema="schemas/MetricSummary.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE, "pcs-bench"],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "metric_id",
            "score",
            "applicability",
            "numerator",
            "denominator",
            "reason",
            "details",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE, "pcs-bench"],
        release_mode_required=False,
    ),
    "ConformanceRun.v0": _entry(
        artifact_type="ConformanceRun.v0",
        schema="schemas/ConformanceRun.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "run_id",
            "suite",
            "status",
            "checks_passed",
            "checks_failed",
            "failures",
            "started_at",
            "completed_at",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE],
        release_mode_required=False,
    ),
    "FailureCaseManifest.v0": _entry(
        artifact_type="FailureCaseManifest.v0",
        schema="schemas/FailureCaseManifest.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "manifest_id",
            "case_id",
            "task_id",
            "failure_code",
            "responsible_component",
            "repair_hint_kind",
            "message",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE],
        release_mode_required=False,
    ),
    "FailureLocalizationResult.v0": _entry(
        artifact_type="FailureLocalizationResult.v0",
        schema="schemas/FailureLocalizationResult.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "result_id",
            "run_id",
            "case_id",
            "expected_failure_code",
            "observed_failure_code",
            "expected_responsible_component",
            "observed_responsible_component",
            "localized_correctly",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE],
        release_mode_required=False,
    ),
    "CoverageReport.v0": _entry(
        artifact_type="CoverageReport.v0",
        schema="schemas/CoverageReport.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "coverage_id",
            "metric",
            "numerator",
            "denominator",
            "coverage_ratio",
            "details",
            "source_repo",
            "source_commit",
            "signature_or_digest",
        ],
        semantic_checks=[],
        consumer_repos=[PCS_CORE],
        release_mode_required=False,
    ),
    "ArtifactRegistry.v0": _entry(
        artifact_type="ArtifactRegistry.v0",
        schema="schemas/ArtifactRegistry.v0.schema.json",
        schema_owner=PCS_CORE,
        runtime_producer=PCS_CORE,
        allowed_runtime_producers=[PCS_CORE],
        allowed_statuses=["Draft", "Validated", "Deprecated"],
        required_release_fields=[
            "schema_version",
            "registry_id",
            "registry_version",
            "entries",
            "signature_or_digest",
        ],
        semantic_checks=[
            _sc("entries_cover_required_artifact_types", "required", PCS_CORE),
        ],
        consumer_repos=[PCS_CORE, LABTRUST, CERTIFYEDGE, PF, SM],
        release_mode_required=False,
    ),

    "PFCorePrincipal.v0": _pf_core_primitive_entry("PFCorePrincipal.v0"),
    "PFCoreCapability.v0": _pf_core_primitive_entry("PFCoreCapability.v0"),
    "PFCoreResource.v0": _pf_core_primitive_entry("PFCoreResource.v0"),
    "PFCoreAction.v0": _pf_core_primitive_entry("PFCoreAction.v0"),
    "PFCoreEvent.v0": _pf_core_primitive_entry(
        "PFCoreEvent.v0",
        runtime_producer=AGENT_RUNTIME,
    ),
    "PFCoreContract.v0": _pf_core_primitive_entry("PFCoreContract.v0"),
    "PFCoreHandoff.v0": _pf_core_primitive_entry("PFCoreHandoff.v0"),
    "PFCoreTrace.v0": _pf_core_release_entry(
        "PFCoreTrace.v0",
        id_field="trace_id",
        extra_release_fields=["trace_hash", "events"],
    ),
    "PFCoreCertificate.v0": _pf_core_release_entry(
        "PFCoreCertificate.v0",
        id_field="certificate_id",
        extra_release_fields=["trace_hash", "claim_class"],
    ),
    "PFCoreRuntimeObservation.v0": _pf_core_release_entry(
        "PFCoreRuntimeObservation.v0",
        id_field="observation_id",
        runtime_producer=AGENT_RUNTIME,
        extra_release_fields=["observed_at", "payload_hash"],
    ),

}


def registry_entries() -> dict[str, dict[str, Any]]:
    return {key: dict(value) for key, value in _REGISTRY_ENTRIES.items()}


def registry_semantic_check_ref(artifact_type: str, check_id: str) -> str:
    return f"{artifact_type}.{check_id}"


def all_registry_semantic_check_refs() -> set[str]:
    refs: set[str] = set()
    for artifact_type, entry in registry_entries().items():
        for check in entry.get("semantic_checks", []):
            if isinstance(check, dict) and check.get("check_id"):
                refs.add(registry_semantic_check_ref(artifact_type, str(check["check_id"])))
    return refs

def pf_core_artifact_types() -> frozenset[str]:
    return _PF_CORE_ARTIFACT_TYPES


_PROOF_OVERCLAIM_CLASSES = frozenset({"LeanKernelChecked", "ProofChecked"})

_ASSUMPTION_REF_PREFIXES = (
    "docs/",
    "examples/",
    "as-",
    "AssumptionSet",
)



_PF_CORE_DEFERRABLE_CHECK_IDS = frozenset({"lean_kernel_proof", "lean_library_build"})


def deferred_registry_obligations(artifact_type: str) -> list[dict[str, Any]]:
    """Return registry semantic checks that may be deferred with assumption refs."""
    entry = _REGISTRY_ENTRIES.get(artifact_type)
    if not entry:
        return []
    checks = entry.get("semantic_checks")
    if not isinstance(checks, list):
        return []
    return [
        check
        for check in checks
        if isinstance(check, dict)
        and (
            check.get("allowed_to_skip")
            or str(check.get("check_id") or "") in _PF_CORE_DEFERRABLE_CHECK_IDS
        )
    ]



def infer_skipped_registry_checks(
    certificate: dict[str, Any],
    *,
    deferred_checks: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Infer which deferrable registry checks were not satisfied by the certificate."""
    artifact_type = str(certificate.get("artifact_type") or "PFCoreCertificate.v0")
    deferred = deferred_checks or deferred_registry_obligations(artifact_type)
    skipped: list[str] = []
    for check in deferred:
        check_id = str(check.get("check_id") or "")
        if check_id == "lean_kernel_proof" and not certificate.get("lean_proof_checked"):
            skipped.append(check_id)
        elif check_id == "lean_library_build":
            build = certificate.get("lean_build_status")
            if not isinstance(build, dict) or not build.get("ok"):
                skipped.append(check_id)
    return skipped



def _assumption_ref_valid(ref: str) -> bool:
    text = ref.strip()
    if not text:
        return False
    if text.endswith(".md") or text.endswith(".json"):
        return True
    if text.startswith(_ASSUMPTION_REF_PREFIXES):
        return True
    return False



def enforce_assumption_declared(
    certificate: dict[str, Any],
    registry_context: dict[str, Any] | None = None,
) -> list[str]:
    """
    Enforce AssumptionDeclared rules when deferrable registry checks were skipped.

    Certificates must not claim LeanKernelChecked or ProofChecked when deferred
    obligations were not executed. Skipped checks require non-empty assumption_refs
    pointing at AssumptionSet.v0 artifacts or documented assumption paths.
    """
    artifact_type = str(certificate.get("artifact_type") or "PFCoreCertificate.v0")
    context = registry_context or _REGISTRY_ENTRIES.get(artifact_type, {})
    explicit_skipped = context.get("skipped_checks")
    if isinstance(explicit_skipped, list):
        skipped = [str(item) for item in explicit_skipped]
    else:
        deferred = context.get("semantic_checks")
        deferred_checks = (
            [check for check in deferred if isinstance(check, dict) and check.get("allowed_to_skip")]
            if isinstance(deferred, list)
            else deferred_registry_obligations(artifact_type)
        )
        skipped = infer_skipped_registry_checks(certificate, deferred_checks=deferred_checks)

    if not skipped:
        return []

    issues: list[str] = []
    claim_class = str(certificate.get("claim_class") or "")
    if claim_class in _PROOF_OVERCLAIM_CLASSES:
        issues.append(
            f"root: claim_class {claim_class!r} forbidden when deferred registry checks "
            f"were skipped: {', '.join(skipped)}"
        )

    refs = certificate.get("assumption_refs")
    if not isinstance(refs, list) or not refs:
        issues.append(
            "root: deferred registry checks require non-empty assumption_refs "
            "(AssumptionSet.v0 id or docs/pf-core/*.md)"
        )
    elif not any(_assumption_ref_valid(str(ref)) for ref in refs):
        issues.append(
            "root: assumption_refs must reference AssumptionSet.v0 ids or documented "
            "assumption paths when registry checks are deferred"
        )
    elif claim_class not in {"AssumptionDeclared", "RuntimeChecked", "CertificateChecked", "ReplayValidated", "SchemaValidated", "OutOfScope"}:
        if claim_class in _PROOF_OVERCLAIM_CLASSES or claim_class == "LeanKernelChecked":
            pass  # already reported
        elif skipped:
            issues.append(
                f"root: deferred registry checks require claim_class AssumptionDeclared "
                f"(got {claim_class!r})"
            )

    return issues



PF_CORE_TRACE_CLAIM_CLASSES = frozenset(
    {
        "SchemaValidated",
        "RuntimeChecked",
        "ReplayValidated",
        "AssumptionDeclared",
        "OutOfScope",
    }
)

PF_CORE_CERTIFICATE_CLAIM_CLASSES = frozenset(
    {
        "SchemaValidated",
        "RuntimeChecked",
        "CertificateChecked",
        "LeanKernelChecked",
        "ReplayValidated",
        "AssumptionDeclared",
        "OutOfScope",
    }
)

PF_CORE_CLAIM_CLASSES = PF_CORE_TRACE_CLAIM_CLASSES | PF_CORE_CERTIFICATE_CLAIM_CLASSES

