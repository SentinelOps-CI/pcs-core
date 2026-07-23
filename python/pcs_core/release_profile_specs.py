"""Registered declarative release-profile specs for PCS domains.

Compatibility wrappers in ``release_chain``, ``tool_use_release_chain``, and
``computation_release_chain`` delegate to the engine with these specs. Domain
logic is expressed as declarative bindings (JSON Pointer) plus optional
semantic/alignment hooks — not separate release-chain validator modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pcs_core.computation_release_chain import (
    COMPUTATION_COMMIT_KEYS,
    COMPUTATION_HANDOFF_FILES,
    COMPUTATION_MANIFEST_ARTIFACTS,
    COMPUTATION_RELEASE_PCS_ARTIFACTS,
    _validate_computation_alignment,
    _validate_computation_scientific_memory_report,
)
from pcs_core.computation_validate import (
    COMPUTATION_RUN_RECEIPT_FILE,
    COMPUTATION_WITNESS_FILE,
    DATASET_RECEIPT_FILE,
    DUPLICATE_RESULT_DECLARATION,
    ENVIRONMENT_RECEIPT_FILE,
    PAYLOAD_DIGEST_MISMATCH,
    PAYLOAD_MISSING,
    PAYLOAD_PATH_UNSAFE,
    PAYLOAD_SIZE_MISMATCH,
    RESULT_ARTIFACT_FILE,
    validate_computation_run_receipt_semantics,
    validate_computation_witness_semantics,
    validate_dataset_receipt_semantics,
    validate_environment_receipt_semantics,
    validate_result_artifact_semantics,
    validate_result_payloads_in_release,
)
from pcs_core.release_profile_engine import (
    ArrayElementBan,
    BundleIdentityBinding,
    CertificateIdBinding,
    ImportRequirement,
    ProofRequirement,
    ProvenanceCommitRequirement,
    ReleaseProfileSpec,
    SignatureRequirement,
    SourceCommitRequirement,
    StatusRequirement,
    register_release_profile,
)
from pcs_core.release_chain import (
    _validate_scientific_memory_report_json,
    _validate_trace_json,
)
from pcs_core.release_chain_profiles import (
    COMPUTATION_WORKFLOW_PROFILE_ID,
    LABTRUST_WORKFLOW_PROFILE_ID,
    TOOL_USE_WORKFLOW_PROFILE_ID,
)
from pcs_core.release_fixtures import (
    CERTIFYEDGE_SOURCE_REPO,
    COMMIT_KEYS,
    LABTRUST_SOURCE_REPO,
    MANIFEST_ARTIFACTS,
    PF_SOURCE_REPO,
    RELEASE_PCS_ARTIFACTS,
    _validate_trace_hash_alignment,
)
from pcs_core.tool_use_release_chain import (
    TOOL_USE_COMMIT_KEYS,
    TOOL_USE_HANDOFF_FILES,
    TOOL_USE_MANIFEST_ARTIFACTS,
    TOOL_USE_RELEASE_PCS_ARTIFACTS,
    _validate_tool_use_scientific_memory_report,
    _validate_tool_use_trace_hash_alignment,
    _validate_tool_use_trace_json,
)
from pcs_core.validate import ValidationError, validate_file

LABTRUST_HANDOFF_FILES = (
    "handoff_to_certifyedge.json",
    "handoff_to_pf.json",
    "handoff_manifest.runtime_to_certificate.v0.json",
    "handoff_manifest.certificate_to_bundle.v0.json",
    "handoff_manifest.bundle_to_verifier.v0.json",
    "handoff_manifest.signed_bundle_to_memory.v0.json",
)


def labtrust_legacy_validator(directory: Path):
    """Parity harness: LabTrust legacy body (not used in production path)."""
    from pcs_core.release_chain import _validate_labtrust_release_chain_impl

    return _validate_labtrust_release_chain_impl(directory)


def tool_use_legacy_validator(directory: Path):
    """Parity harness: tool-use legacy body (not used in production path)."""
    from pcs_core.tool_use_release_chain import _validate_tool_use_release_chain_impl

    return _validate_tool_use_release_chain_impl(directory)


def computation_legacy_validator(directory: Path):
    """Parity harness: computation legacy body (not used in production path)."""
    from pcs_core.computation_release_chain import _validate_computation_release_chain_impl

    return _validate_computation_release_chain_impl(directory)


def _computation_semantic_issue_code(artifact: str, message: str) -> str:
    if artifact == COMPUTATION_RUN_RECEIPT_FILE:
        if "missing_code_commit" in message or "zero" in message:
            return "missing_code_commit"
        if "exit_code" in message:
            return "nonzero_exit_code"
    return "schema_validation_failed"


def _tool_use_alignment_issue_code(message: str) -> str:
    if "policy_hash" in message:
        return "policy_hash_mismatch"
    return "trace_hash_mismatch"


def _computation_alignment_issue_code(message: str) -> str:
    if "dataset_hash" in message:
        return "dataset_hash_mismatch"
    if "environment_hash" in message:
        return "environment_hash_mismatch"
    if "result_hashes" in message:
        return "result_hash_mismatch"
    if "run_receipt_hash" in message:
        return "run_receipt_hash_mismatch"
    if "nonzero_exit_code" in message or "exit_code" in message:
        return "nonzero_exit_code"
    if "code_commit" in message:
        return "missing_code_commit"
    return "schema_validation_failed"


def _tool_use_domain_checks(
    base: Path,
    _manifest: dict[str, Any],
    _commits: dict[str, Any],
    issues: list,
) -> None:
    from pcs_core.release_chain import _issue
    from pcs_core.release_fixtures import _load_json

    manifest_v0 = _load_json(base / "release_manifest.v0.json")
    if manifest_v0:
        if manifest_v0.get("workflow_profile_id") != TOOL_USE_WORKFLOW_PROFILE_ID:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    "release_manifest.v0.json workflow_profile_id must match tool-use profile",
                ),
            )
        try:
            validate_file(base / "release_manifest.v0.json")
        except ValidationError as exc:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    f"release_manifest.v0.json: pcs validate failed: {exc}",
                    artifact="release_manifest.v0.json",
                ),
            )


def _computation_payload_issue_code(message: str) -> str:
    if DUPLICATE_RESULT_DECLARATION in message:
        return DUPLICATE_RESULT_DECLARATION
    if PAYLOAD_DIGEST_MISMATCH in message:
        return PAYLOAD_DIGEST_MISMATCH
    if PAYLOAD_SIZE_MISMATCH in message:
        return PAYLOAD_SIZE_MISMATCH
    if PAYLOAD_PATH_UNSAFE in message:
        return PAYLOAD_PATH_UNSAFE
    if PAYLOAD_MISSING in message:
        return PAYLOAD_MISSING
    return "schema_validation_failed"


def _computation_domain_checks(
    base: Path,
    _manifest: dict[str, Any],
    _commits: dict[str, Any],
    issues: list,
) -> None:
    from pcs_core.release_chain import _issue
    from pcs_core.release_fixtures import _load_json

    witness = _load_json(base / COMPUTATION_WITNESS_FILE)
    if witness and witness.get("status") != "CertificateChecked":
        if witness.get("status") == "Rejected":
            issues.append(
                _issue(
                    "rejected_computation_witness",
                    "computation_witness.status is Rejected",
                ),
            )
        else:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    "computation_witness.status must be CertificateChecked",
                ),
            )

    for msg in validate_result_payloads_in_release(base):
        issues.append(
            _issue(
                _computation_payload_issue_code(msg),
                msg,
                artifact=RESULT_ARTIFACT_FILE,
            ),
        )

    manifest_v0 = _load_json(base / "release_manifest.v0.json")
    if manifest_v0:
        if manifest_v0.get("workflow_profile_id") != COMPUTATION_WORKFLOW_PROFILE_ID:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    "release_manifest.v0.json workflow_profile_id must match computation profile",
                ),
            )
        try:
            validate_file(base / "release_manifest.v0.json")
        except ValidationError as exc:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    f"release_manifest.v0.json: pcs validate failed: {exc}",
                    artifact="release_manifest.v0.json",
                ),
            )


LABTRUST_RELEASE_PROFILE = register_release_profile(
    ReleaseProfileSpec(
        workflow_profile_id=LABTRUST_WORKFLOW_PROFILE_ID,
        required_artifacts=MANIFEST_ARTIFACTS,
        release_pcs_artifacts=RELEASE_PCS_ARTIFACTS,
        handoff_files=LABTRUST_HANDOFF_FILES,
        commit_keys=COMMIT_KEYS,
        enforce_manifest_workflow_id=False,
        handoff_require_complete=False,
        handoff_enforce_order=True,
        semantic_validators={
            "trace.json": _validate_trace_json,
            "scientific_memory_import_report.json": _validate_scientific_memory_report_json,
        },
        alignment_checker=_validate_trace_hash_alignment,
        alignment_issue_mapper=lambda _msg: "trace_hash_mismatch",
        status_requirements=(
            StatusRequirement(
                artifact="verification_result.json",
                pointer="/status",
                required_value="ProofChecked",
                issue_code="schema_validation_failed",
            ),
            StatusRequirement(
                artifact="trace_certificate.json",
                pointer="/status",
                required_value="CertificateChecked",
                issue_code="schema_validation_failed",
            ),
            StatusRequirement(
                artifact="signed_science_claim_bundle.json",
                pointer="/verification_result/status",
                required_value="ProofChecked",
                issue_code="schema_validation_failed",
            ),
        ),
        source_commit_requirements=(
            SourceCommitRequirement(
                artifact="runtime_receipt.json",
                pointer="/source_commit",
                manifest_commit_key="labtrust_gym_commit",
                issue_code="labtrust_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="trace_certificate.json",
                pointer="/source_commit",
                manifest_commit_key="certifyedge_commit",
                issue_code="certifyedge_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="verification_result.json",
                pointer="/source_commit",
                manifest_commit_key="provability_fabric_commit",
                issue_code="pf_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="signed_science_claim_bundle.json",
                pointer="/source_commit",
                manifest_commit_key="provability_fabric_commit",
                issue_code="pf_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="scientific_memory_import_report.json",
                pointer="/source_commit",
                manifest_commit_key="scientific_memory_commit",
                issue_code="scientific_memory_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="scientific_memory_import_report.json",
                pointer="/scientific_memory_commit",
                manifest_commit_key="scientific_memory_commit",
                issue_code="scientific_memory_commit_mismatch",
            ),
        ),
        provenance_commit_requirements=(
            ProvenanceCommitRequirement(
                artifact="science_claim_bundle.pending.json",
                expected_repo=LABTRUST_SOURCE_REPO,
                manifest_commit_key="labtrust_gym_commit",
                issue_code="labtrust_commit_mismatch",
            ),
            ProvenanceCommitRequirement(
                artifact="science_claim_bundle.certified.json",
                expected_repo=LABTRUST_SOURCE_REPO,
                manifest_commit_key="labtrust_gym_commit",
                issue_code="labtrust_commit_mismatch",
            ),
            ProvenanceCommitRequirement(
                artifact="signed_science_claim_bundle.json",
                expected_repo=LABTRUST_SOURCE_REPO,
                manifest_commit_key="labtrust_gym_commit",
                issue_code="labtrust_commit_mismatch",
                nested_root_pointer="/science_claim_bundle",
            ),
            ProvenanceCommitRequirement(
                artifact="science_claim_bundle.certified.json",
                expected_repo=CERTIFYEDGE_SOURCE_REPO,
                manifest_commit_key="certifyedge_commit",
                issue_code="certifyedge_commit_mismatch",
            ),
            ProvenanceCommitRequirement(
                artifact="signed_science_claim_bundle.json",
                expected_repo=CERTIFYEDGE_SOURCE_REPO,
                manifest_commit_key="certifyedge_commit",
                issue_code="certifyedge_commit_mismatch",
            ),
            ProvenanceCommitRequirement(
                artifact="verification_result.json",
                expected_repo=PF_SOURCE_REPO,
                manifest_commit_key="provability_fabric_commit",
                issue_code="pf_commit_mismatch",
            ),
            ProvenanceCommitRequirement(
                artifact="signed_science_claim_bundle.json",
                expected_repo=PF_SOURCE_REPO,
                manifest_commit_key="provability_fabric_commit",
                issue_code="pf_commit_mismatch",
            ),
        ),
        certificate_bindings=(
            CertificateIdBinding(
                source_artifact="trace_certificate.json",
                source_pointer="/certificate_id",
                target_artifact="science_claim_bundle.certified.json",
                target_pointer="/certificates/0/certificate_id",
            ),
            CertificateIdBinding(
                source_artifact="trace_certificate.json",
                source_pointer="/certificate_id",
                target_artifact="science_claim_bundle.certified.json",
                target_pointer="/claim_artifact/certificate_refs",
                mode="array_contains",
            ),
            CertificateIdBinding(
                source_artifact="trace_certificate.json",
                source_pointer="/certificate_id",
                target_artifact="science_claim_bundle.certified.json",
                target_pointer="/evidence_bundle/certificate_refs",
                mode="array_contains",
            ),
            CertificateIdBinding(
                source_artifact="trace_certificate.json",
                source_pointer="/certificate_id",
                target_artifact="verification_result.json",
                target_pointer="/verified_input/certificate_id",
            ),
            CertificateIdBinding(
                source_artifact="trace_certificate.json",
                source_pointer="/certificate_id",
                target_artifact="signed_science_claim_bundle.json",
                target_pointer="/science_claim_bundle/certificates/0/certificate_id",
            ),
        ),
        bundle_identity_bindings=(
            BundleIdentityBinding(
                artifact="verification_result.json",
                pointer="/verified_input/bundle_hash",
                issue_code="verified_input_hash_mismatch",
                require_present=True,
            ),
            BundleIdentityBinding(
                artifact="signed_science_claim_bundle.json",
                pointer="/signed_input_bundle_hash",
                issue_code="signed_input_hash_mismatch",
                require_present=True,
            ),
        ),
        import_requirements=(
            ImportRequirement(
                artifact="scientific_memory_import_report.json",
                pointer="/verification_status",
                required_value="passed",
                issue_code="scientific_memory_import_failed",
            ),
            ImportRequirement(
                artifact="scientific_memory_import_report.json",
                pointer="/strict",
                required_value=True,
                issue_code="scientific_memory_import_failed",
            ),
            ImportRequirement(
                artifact="scientific_memory_import_report.json",
                pointer="/allow_legacy",
                required_value=False,
                issue_code="legacy_import_detected",
            ),
            ImportRequirement(
                artifact="scientific_memory_import_report.json",
                pointer="/bundle_shape",
                required_value="pcs_core",
                issue_code="legacy_import_detected",
            ),
        ),
        proof_requirements=(
            ProofRequirement(
                artifact="verification_result.json",
                pointer="/verified_input",
                issue_code="schema_validation_failed",
                message="verification_result.verified_input is required for release chain fixtures",
            ),
        ),
        signature_requirements=(
            SignatureRequirement(
                artifact="signed_science_claim_bundle.json",
                pointer="/signature_or_digest",
            ),
        ),
    ),
)

TOOL_USE_RELEASE_PROFILE = register_release_profile(
    ReleaseProfileSpec(
        workflow_profile_id=TOOL_USE_WORKFLOW_PROFILE_ID,
        required_artifacts=TOOL_USE_MANIFEST_ARTIFACTS,
        release_pcs_artifacts=TOOL_USE_RELEASE_PCS_ARTIFACTS,
        handoff_files=TOOL_USE_HANDOFF_FILES,
        commit_keys=TOOL_USE_COMMIT_KEYS,
        handoff_require_complete=False,
        handoff_enforce_order=True,
        semantic_validators={
            "tool_use_trace.valid.json": _validate_tool_use_trace_json,
            "tool_use_trace.json": _validate_tool_use_trace_json,
            "scientific_memory_import_report.json": _validate_tool_use_scientific_memory_report,
        },
        alignment_checker=_validate_tool_use_trace_hash_alignment,
        alignment_issue_mapper=_tool_use_alignment_issue_code,
        status_requirements=(
            StatusRequirement(
                artifact="verification_result.json",
                pointer="/status",
                required_value="ProofChecked",
                issue_code="schema_validation_failed",
            ),
            StatusRequirement(
                artifact="tool_use_certificate.valid.json",
                pointer="/status",
                required_value="CertificateChecked",
                issue_code="rejected_certificate",
            ),
        ),
        source_commit_requirements=(
            SourceCommitRequirement(
                artifact="tool_use_trace.valid.json",
                pointer="/source_commit",
                manifest_commit_key="agent_runtime_commit",
                issue_code="agent_runtime_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="runtime_receipt.json",
                pointer="/source_commit",
                manifest_commit_key="agent_runtime_commit",
                issue_code="agent_runtime_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="tool_use_certificate.valid.json",
                pointer="/source_commit",
                manifest_commit_key="certifyedge_commit",
                issue_code="certifyedge_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="verification_result.json",
                pointer="/source_commit",
                manifest_commit_key="provability_fabric_commit",
                issue_code="pf_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="signed_science_claim_bundle.json",
                pointer="/source_commit",
                manifest_commit_key="provability_fabric_commit",
                issue_code="pf_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="scientific_memory_import_report.json",
                pointer="/source_commit",
                manifest_commit_key="scientific_memory_commit",
                issue_code="scientific_memory_commit_mismatch",
            ),
        ),
        certificate_bindings=(
            CertificateIdBinding(
                source_artifact="tool_use_certificate.valid.json",
                source_pointer="/certificate_id",
                target_artifact="science_claim_bundle.certified.json",
                target_pointer="/certificates/0/certificate_id",
            ),
            CertificateIdBinding(
                source_artifact="tool_use_certificate.valid.json",
                source_pointer="/certificate_id",
                target_artifact="science_claim_bundle.certified.json",
                target_pointer="/claim_artifact/certificate_refs",
                mode="array_contains",
            ),
        ),
        bundle_identity_bindings=(
            BundleIdentityBinding(
                artifact="verification_result.json",
                pointer="/verified_input/bundle_hash",
                issue_code="verified_input_hash_mismatch",
                require_present=False,
            ),
        ),
        import_requirements=(
            ImportRequirement(
                artifact="scientific_memory_import_report.json",
                pointer="/verification_status",
                required_value="passed",
                issue_code="scientific_memory_import_failed",
            ),
        ),
        array_element_bans=(
            ArrayElementBan(
                artifact="tool_use_trace.valid.json",
                array_pointer="/tool_calls",
                element_pointer="/authorization_status",
                banned_value="rejected",
                issue_code="unauthorized_tool_call",
                message_template="tool_calls[{index}].authorization_status is rejected",
            ),
        ),
        signature_requirements=(
            SignatureRequirement(
                artifact="signed_science_claim_bundle.json",
                pointer="/signature_or_digest",
            ),
        ),
        domain_checks=_tool_use_domain_checks,
    ),
)

COMPUTATION_RELEASE_PROFILE = register_release_profile(
    ReleaseProfileSpec(
        workflow_profile_id=COMPUTATION_WORKFLOW_PROFILE_ID,
        required_artifacts=COMPUTATION_MANIFEST_ARTIFACTS,
        release_pcs_artifacts=COMPUTATION_RELEASE_PCS_ARTIFACTS,
        handoff_files=COMPUTATION_HANDOFF_FILES,
        commit_keys=COMPUTATION_COMMIT_KEYS,
        handoff_require_complete=False,
        handoff_enforce_order=True,
        semantic_validators={
            DATASET_RECEIPT_FILE: validate_dataset_receipt_semantics,
            ENVIRONMENT_RECEIPT_FILE: validate_environment_receipt_semantics,
            COMPUTATION_RUN_RECEIPT_FILE: validate_computation_run_receipt_semantics,
            RESULT_ARTIFACT_FILE: validate_result_artifact_semantics,
            COMPUTATION_WITNESS_FILE: validate_computation_witness_semantics,
            "scientific_memory_import_report.json": _validate_computation_scientific_memory_report,
        },
        semantic_issue_mapper=_computation_semantic_issue_code,
        alignment_checker=_validate_computation_alignment,
        alignment_issue_mapper=_computation_alignment_issue_code,
        status_requirements=(
            StatusRequirement(
                artifact="verification_result.json",
                pointer="/status",
                required_value="ProofChecked",
                issue_code="schema_validation_failed",
            ),
        ),
        source_commit_requirements=(
            SourceCommitRequirement(
                artifact=DATASET_RECEIPT_FILE,
                pointer="/source_commit",
                manifest_commit_key="scientific_computation_commit",
                issue_code="scientific_computation_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact=ENVIRONMENT_RECEIPT_FILE,
                pointer="/source_commit",
                manifest_commit_key="scientific_computation_commit",
                issue_code="scientific_computation_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact=COMPUTATION_RUN_RECEIPT_FILE,
                pointer="/source_commit",
                manifest_commit_key="scientific_computation_commit",
                issue_code="scientific_computation_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact=RESULT_ARTIFACT_FILE,
                pointer="/source_commit",
                manifest_commit_key="scientific_computation_commit",
                issue_code="scientific_computation_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact=COMPUTATION_WITNESS_FILE,
                pointer="/source_commit",
                manifest_commit_key="certifyedge_commit",
                issue_code="certifyedge_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="verification_result.json",
                pointer="/source_commit",
                manifest_commit_key="provability_fabric_commit",
                issue_code="pf_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="signed_science_claim_bundle.json",
                pointer="/source_commit",
                manifest_commit_key="provability_fabric_commit",
                issue_code="pf_commit_mismatch",
            ),
            SourceCommitRequirement(
                artifact="scientific_memory_import_report.json",
                pointer="/source_commit",
                manifest_commit_key="scientific_memory_commit",
                issue_code="scientific_memory_commit_mismatch",
            ),
        ),
        certificate_bindings=(
            CertificateIdBinding(
                source_artifact=COMPUTATION_WITNESS_FILE,
                source_pointer="/witness_id",
                target_artifact="science_claim_bundle.certified.json",
                target_pointer="/certificates/0/certificate_id",
            ),
            CertificateIdBinding(
                source_artifact=COMPUTATION_WITNESS_FILE,
                source_pointer="/witness_id",
                target_artifact="science_claim_bundle.certified.json",
                target_pointer="/claim_artifact/certificate_refs",
                mode="array_contains",
            ),
        ),
        bundle_identity_bindings=(
            BundleIdentityBinding(
                artifact="verification_result.json",
                pointer="/verified_input/bundle_hash",
                issue_code="verified_input_hash_mismatch",
                require_present=False,
            ),
        ),
        import_requirements=(
            ImportRequirement(
                artifact="scientific_memory_import_report.json",
                pointer="/verification_status",
                required_value="passed",
                issue_code="scientific_memory_import_failed",
            ),
        ),
        signature_requirements=(
            SignatureRequirement(
                artifact="signed_science_claim_bundle.json",
                pointer="/signature_or_digest",
            ),
        ),
        domain_checks=_computation_domain_checks,
    ),
)


def parity_profile_specs() -> tuple[ReleaseProfileSpec, ...]:
    """Specs with legacy validators attached for side-by-side parity checks."""
    from dataclasses import replace

    return (
        replace(LABTRUST_RELEASE_PROFILE, legacy_validator=labtrust_legacy_validator),
        replace(TOOL_USE_RELEASE_PROFILE, legacy_validator=tool_use_legacy_validator),
        replace(COMPUTATION_RELEASE_PROFILE, legacy_validator=computation_legacy_validator),
    )
