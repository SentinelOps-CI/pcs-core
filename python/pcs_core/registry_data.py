"""Canonical PCS v0.1 artifact registry entries (protocol authority)."""

from __future__ import annotations

from typing import Any

PCS_CORE = "pcs-core"
LABTRUST = "LabTrust-Gym"
CERTIFYEDGE = "CertifyEdge"
PF = "Provability Fabric"
SM = "Scientific Memory"

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
