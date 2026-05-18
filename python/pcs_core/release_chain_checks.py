"""Release-chain check catalog (30 RC checks) for ReleaseChainValidationResult.v0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pcs_core.release_chain import ReleaseChainIssue
from pcs_core.registry_semantics import responsible_component_for_registry_refs
from pcs_core.release_chain_registry_refs import RELEASE_CHAIN_REGISTRY_CHECK_REFS


@dataclass(frozen=True)
class ReleaseChainCheckSpec:
    check_id: str
    description: str
    failure_codes: frozenset[str]
    registry_check_refs: frozenset[str] = frozenset()


RELEASE_CHAIN_CHECK_SPECS: tuple[ReleaseChainCheckSpec, ...] = (
    ReleaseChainCheckSpec(
        "manifest_present",
        "RELEASE_FIXTURE_MANIFEST.json exists",
        frozenset({"manifest_missing"}),
    ),
    ReleaseChainCheckSpec(
        "artifact_files_present",
        "Every manifest-listed artifact file exists on disk",
        frozenset({"artifact_missing"}),
    ),
    ReleaseChainCheckSpec(
        "manifest_hashes_match",
        "Every artifact hash matches the manifest digest",
        frozenset({"manifest_hash_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "forbidden_provenance_values",
        "No local_dev, zero commits, or pattern placeholder commits in artifacts",
        frozenset(
            {
                "local_dev_detected",
                "placeholder_commit_detected",
                "schema_validation_failed",
            },
        ),
    ),
    ReleaseChainCheckSpec(
        "runtime_receipt_labtrust_commit",
        "runtime_receipt.json source_commit matches manifest.labtrust_gym_commit",
        frozenset({"labtrust_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "pending_bundle_labtrust_commits",
        "science_claim_bundle.pending.json LabTrust provenance matches manifest",
        frozenset({"labtrust_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "certified_bundle_labtrust_commits",
        "science_claim_bundle.certified.json LabTrust provenance matches manifest",
        frozenset({"labtrust_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "signed_bundle_nested_labtrust_commits",
        "signed bundle nested science_claim_bundle LabTrust commits match manifest",
        frozenset({"labtrust_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "trace_certificate_certifyedge_commit",
        "trace_certificate.json source_commit matches manifest.certifyedge_commit",
        frozenset({"certifyedge_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "certified_bundle_certifyedge_commits",
        "certified bundle CertifyEdge provenance matches manifest",
        frozenset({"certifyedge_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "signed_bundle_certifyedge_commits",
        "signed bundle CertifyEdge provenance matches manifest",
        frozenset({"certifyedge_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "verification_result_pf_commit",
        "verification_result.json source_commit matches manifest.provability_fabric_commit",
        frozenset({"pf_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "signed_bundle_pf_commit",
        "signed_science_claim_bundle.json source_commit matches manifest",
        frozenset({"pf_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "verification_nested_pf_commits",
        "verification_result nested PF provenance matches manifest",
        frozenset({"pf_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "signed_nested_pf_commits",
        "signed bundle nested PF provenance matches manifest",
        frozenset({"pf_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "scientific_memory_source_commit",
        "Scientific Memory report source_commit matches manifest",
        frozenset({"scientific_memory_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "scientific_memory_pin_commit",
        "Scientific Memory report scientific_memory_commit matches manifest",
        frozenset({"scientific_memory_commit_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "certificate_id_trace_certificate",
        "certificate_id on trace_certificate is present and consistent",
        frozenset({"certificate_id_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "certificate_id_certified_bundle",
        "certificate_id matches on certified bundle certificates",
        frozenset({"certificate_id_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "certificate_id_claim_refs",
        "certificate_id referenced from certified claim_artifact",
        frozenset({"certificate_id_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "certificate_id_evidence_refs",
        "certificate_id referenced from certified evidence_bundle",
        frozenset({"certificate_id_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "certificate_id_verification",
        "certificate_id matches verification_result.verified_input",
        frozenset({"certificate_id_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "certificate_id_signed_bundle",
        "certificate_id matches signed bundle embedded certificates",
        frozenset({"certificate_id_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "trace_hash_alignment",
        "trace_hash is identical across trace, receipt, certificate, verification, signed bundle",
        frozenset({"trace_hash_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "verified_input_bundle_hash",
        "verification_result.verified_input.bundle_hash matches certified bundle manifest hash",
        frozenset({"verified_input_hash_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "signed_input_bundle_hash",
        "signed_science_claim_bundle.signed_input_bundle_hash matches certified manifest hash",
        frozenset({"signed_input_hash_mismatch"}),
    ),
    ReleaseChainCheckSpec(
        "scientific_memory_import_passed",
        "scientific_memory_import_report.verification_status is passed",
        frozenset({"scientific_memory_import_failed"}),
    ),
    ReleaseChainCheckSpec(
        "scientific_memory_strict_import",
        "scientific_memory_import_report.strict is true",
        frozenset({"scientific_memory_import_failed"}),
    ),
    ReleaseChainCheckSpec(
        "scientific_memory_no_legacy",
        "scientific_memory_import_report.allow_legacy is false and bundle_shape is pcs_core",
        frozenset({"legacy_import_detected", "scientific_memory_import_failed"}),
    ),
    ReleaseChainCheckSpec(
        "pcs_artifact_schema_validation",
        "PCS JSON artifacts pass pcs validate schema and semantics",
        frozenset({"schema_validation_failed"}),
    ),
)

RELEASE_CHAIN_CHECK_COUNT = len(RELEASE_CHAIN_CHECK_SPECS)


def build_checks_from_issues(issues: list[ReleaseChainIssue]) -> list[dict[str, Any]]:
    """Map validator issues to the 30-check catalog."""
    codes = {issue.code for issue in issues}
    checks: list[dict[str, Any]] = []
    for spec in RELEASE_CHAIN_CHECK_SPECS:
        failed = bool(codes & spec.failure_codes) and bool(issues)
        if not issues:
            status = "passed"
        elif failed:
            status = "failed"
        else:
            status = "passed"
        matching = [issue for issue in issues if issue.code in spec.failure_codes]
        details: dict[str, Any] = {}
        if matching:
            details = {
                "failure_code": matching[0].code,
                "message": matching[0].message,
            }
            if matching[0].artifact:
                details["artifact"] = matching[0].artifact
        refs = spec.registry_check_refs or frozenset(
            RELEASE_CHAIN_REGISTRY_CHECK_REFS.get(spec.check_id, ()),
        )
        checks.append(
            {
                "check_id": spec.check_id,
                "description": spec.description,
                "status": status,
                "details": details,
                "registry_check_refs": sorted(refs),
                "responsible_component": responsible_component_for_registry_refs(refs),
            },
        )
    return checks
