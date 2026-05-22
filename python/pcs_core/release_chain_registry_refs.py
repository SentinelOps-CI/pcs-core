"""Maps release-chain check_id values to ArtifactRegistry semantic check refs."""

from __future__ import annotations

RELEASE_CHAIN_REGISTRY_CHECK_REFS: dict[str, tuple[str, ...]] = {
    "manifest_present": (),
    "artifact_files_present": ("ReleaseManifest.v0.artifact_hashes_match_files",),
    "manifest_hashes_match": ("ReleaseManifest.v0.artifact_hashes_match_files",),
    "forbidden_provenance_values": ("ReleaseManifest.v0.release_mode_commit_policy",),
    "runtime_receipt_labtrust_commit": (
        "RuntimeReceipt.v0.source_commit_matches_release_manifest",
    ),
    "pending_bundle_labtrust_commits": ("ScienceClaimBundle.v0.non_empty_runtime_receipts",),
    "certified_bundle_labtrust_commits": (
        "ScienceClaimBundle.v0.certified_bundle_has_certificate_when_checked",
    ),
    "signed_bundle_nested_labtrust_commits": (
        "SignedScienceClaimBundle.v0.embedded_bundle_passes_science_claim_semantics",
    ),
    "trace_certificate_certifyedge_commit": (
        "TraceCertificate.v0.source_commit_matches_release_manifest",
    ),
    "certified_bundle_certifyedge_commits": (
        "ScienceClaimBundle.v0.certified_bundle_has_certificate_when_checked",
    ),
    "signed_bundle_certifyedge_commits": (
        "SignedScienceClaimBundle.v0.embedded_bundle_passes_science_claim_semantics",
    ),
    "verification_result_pf_commit": (
        "VerificationResult.v0.verified_input_bundle_hash_matches_certified",
    ),
    "signed_bundle_pf_commit": (
        "SignedScienceClaimBundle.v0.signed_input_bundle_hash_matches_certified",
    ),
    "verification_nested_pf_commits": (
        "VerificationResult.v0.failed_checks_block_import_ready_status",
    ),
    "signed_nested_pf_commits": (
        "SignedScienceClaimBundle.v0.signed_input_bundle_hash_matches_certified",
    ),
    "scientific_memory_source_commit": (),
    "scientific_memory_pin_commit": (),
    "certificate_id_trace_certificate": (
        "TraceCertificate.v0.status_is_certificate_checked_for_release",
    ),
    "certificate_id_certified_bundle": (
        "ScienceClaimBundle.v0.certified_bundle_has_certificate_when_checked",
    ),
    "certificate_id_claim_refs": ("EvidenceBundle.v0.certificate_refs_resolve",),
    "certificate_id_evidence_refs": ("EvidenceBundle.v0.certificate_refs_resolve",),
    "certificate_id_verification": (
        "VerificationResult.v0.verified_input_bundle_hash_matches_certified",
    ),
    "certificate_id_signed_bundle": (
        "SignedScienceClaimBundle.v0.signed_input_bundle_hash_matches_certified",
    ),
    "trace_hash_alignment": (
        "TraceCertificate.v0.trace_hash_matches_runtime_receipt",
        "RuntimeReceipt.v0.trace_hash_present",
    ),
    "verified_input_bundle_hash": (
        "VerificationResult.v0.verified_input_bundle_hash_matches_certified",
    ),
    "signed_input_bundle_hash": (
        "SignedScienceClaimBundle.v0.signed_input_bundle_hash_matches_certified",
    ),
    "scientific_memory_import_passed": (),
    "scientific_memory_strict_import": (),
    "scientific_memory_no_legacy": (),
    "pcs_artifact_schema_validation": (
        "ArtifactRegistry.v0.entries_cover_required_artifact_types",
    ),
}
