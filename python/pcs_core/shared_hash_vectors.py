"""Shared canonical hash vectors for Python, Rust, and TypeScript."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.hash import canonical_hash, canonical_json_bytes
from pcs_core.paths import package_dir, repo_root

VECTOR_SPECS: dict[str, str] = {
    "RuntimeReceipt.v0": "examples/runtime_receipt.valid.json",
    "TraceCertificate.v0": "examples/trace_certificate.valid.json",
    "ScienceClaimBundle.v0": "examples/science_claim_bundle.certified.valid.json",
    "SignedScienceClaimBundle.v0": "examples/signed_science_claim_bundle.valid.json",
    "ReleaseManifest.v0": "examples/release_manifest.valid.json",
    "HandoffManifest.v0": "examples/handoff_manifest.valid.json",
    "ReleaseChainValidationResult.v0": "examples/release_chain_validation_result.valid.json",
    "ComponentReleaseFragment.v0": "examples/component_release_fragment.valid.json",
    "ArtifactRegistry.v0": "examples/artifact_registry.valid.json",
    "SemanticCheckExecution.v0": "examples/semantic_check_execution.valid.json",
    "WorkflowProfile.v0": "examples/workflow_profiles/agent_tool_use_safety.valid.json",
    "ToolUseTrace.v0": "examples/tool_use_trace.valid.json",
    "ToolUseCertificate.v0": "examples/tool_use_certificate.valid.json",
    "DatasetReceipt.v0": "examples/dataset_receipt.valid.json",
    "EnvironmentReceipt.v0": "examples/environment_receipt.valid.json",
    "ComputationRunReceipt.v0": "examples/computation_run_receipt.valid.json",
    "ResultArtifact.v0": "examples/result_artifact.valid.json",
    "ComputationWitness.v0": "examples/computation_witness.valid.json",
    "VerifierProfile.v1": "examples/verifier_assurance/valid/profile_basic/profile.json",
    "VerificationResult.v1": "examples/verifier_assurance/valid/result_accept/result.json",
    "VerifierInvocationRecord.v1": "examples/verifier_assurance/valid/invocation_basic/invocation.json",
    "VerifierReplayReport.v1": "examples/verifier_assurance/valid/replay_matched/replay.json",
    "VerifierMutationManifest.v1": "examples/verifier_assurance/valid/mutation_timeout/mutation.json",
    "RewardEvidenceEnvelope.v1": "examples/verifier_assurance/valid/reward_scalar/reward.json",
    "OptimizationCampaignManifest.v1": "examples/verifier_assurance/valid/campaign_basic/campaign.json",
    "AdjudicationRecord.v1": "examples/verifier_assurance/valid/adjudication_basic/adjudication.json",
    "VerifierAssuranceReport.v1": "examples/verifier_assurance/valid/report_rebuild/report.json",
}

VECTOR_FILENAMES: dict[str, str] = {
    "RuntimeReceipt.v0": "runtime_receipt.vector.json",
    "TraceCertificate.v0": "trace_certificate.vector.json",
    "ScienceClaimBundle.v0": "science_claim_bundle.vector.json",
    "SignedScienceClaimBundle.v0": "signed_science_claim_bundle.vector.json",
    "ReleaseManifest.v0": "release_manifest.vector.json",
    "HandoffManifest.v0": "handoff_manifest.vector.json",
    "ReleaseChainValidationResult.v0": "release_chain_validation_result.vector.json",
    "ComponentReleaseFragment.v0": "component_release_fragment.vector.json",
    "ArtifactRegistry.v0": "artifact_registry.vector.json",
    "SemanticCheckExecution.v0": "semantic_check_execution.vector.json",
    "WorkflowProfile.v0": "workflow_profile.vector.json",
    "ToolUseTrace.v0": "tool_use_trace.vector.json",
    "ToolUseCertificate.v0": "tool_use_certificate.vector.json",
    "DatasetReceipt.v0": "dataset_receipt.vector.json",
    "EnvironmentReceipt.v0": "environment_receipt.vector.json",
    "ComputationRunReceipt.v0": "computation_run_receipt.vector.json",
    "ResultArtifact.v0": "result_artifact.vector.json",
    "ComputationWitness.v0": "computation_witness.vector.json",
    "VerifierProfile.v1": "verifierprofile_v1.vector.json",
    "VerificationResult.v1": "verificationresult_v1.vector.json",
    "VerifierInvocationRecord.v1": "verifierinvocationrecord_v1.vector.json",
    "VerifierReplayReport.v1": "verifierreplayreport_v1.vector.json",
    "VerifierMutationManifest.v1": "verifiermutationmanifest_v1.vector.json",
    "RewardEvidenceEnvelope.v1": "rewardevidenceenvelope_v1.vector.json",
    "OptimizationCampaignManifest.v1": "optimizationcampaignmanifest_v1.vector.json",
    "AdjudicationRecord.v1": "adjudicationrecord_v1.vector.json",
    "VerifierAssuranceReport.v1": "verifierassurancereport_v1.vector.json",
}


def shared_vectors_dir() -> Path:
    bundled = package_dir() / "test_vectors" / "hash"
    if bundled.is_dir() and any(bundled.glob("*.vector.json")):
        return bundled
    return repo_root() / "test_vectors" / "hash"


def vector_path(artifact_type: str) -> Path:
    return shared_vectors_dir() / VECTOR_FILENAMES[artifact_type]


def load_vector(artifact_type: str) -> dict[str, Any]:
    return json.loads(vector_path(artifact_type).read_text(encoding="utf-8"))


def _example_path(relative: str) -> Path:
    return repo_root() / relative


def write_shared_vectors(*, force: bool = False) -> None:
    out_dir = shared_vectors_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    allowed = set(VECTOR_FILENAMES.values())
    for path in out_dir.glob("*.vector.json"):
        if path.name not in allowed:
            path.unlink()
    for artifact_type, relative in VECTOR_SPECS.items():
        path = vector_path(artifact_type)
        if path.exists() and not force:
            continue
        example = _example_path(relative)
        if not example.is_file():
            continue
        data = json.loads(example.read_text(encoding="utf-8"))
        payload = {
            "artifact_type": artifact_type,
            "input_file": relative.replace("\\", "/"),
            "expected_digest": canonical_hash(data),
            "canonical_json": canonical_json_bytes(data).decode("utf-8"),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def verify_shared_vectors() -> list[str]:
    errors: list[str] = []
    for artifact_type, relative in VECTOR_SPECS.items():
        vector = load_vector(artifact_type)
        example_name = str(vector.get("input", vector.get("input_file", relative))).replace(
            "\\", "/"
        )
        if not example_name.startswith("examples/"):
            example_name = relative
        data = json.loads(_example_path(example_name).read_text(encoding="utf-8"))
        expected_digest = str(vector["expected_digest"])
        expected_canonical = str(vector["canonical_json"])
        actual_digest = canonical_hash(data)
        actual_canonical = canonical_json_bytes(data).decode("utf-8")
        if actual_digest != expected_digest:
            errors.append(
                f"{artifact_type}: digest mismatch "
                f"(expected {expected_digest}, got {actual_digest})",
            )
        if actual_canonical != expected_canonical:
            errors.append(f"{artifact_type}: canonical JSON drift")
    return errors
