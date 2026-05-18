#!/usr/bin/env python3
"""Write tool-use workflow profiles and conformance release fixtures."""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash  # noqa: E402
from pcs_core.paths import examples_dir  # noqa: E402
from pcs_core.protocol_fixtures import (  # noqa: E402
    CERTIFYEDGE_REPO,
    PF_REPO,
    PCS_CORE_REPO,
    SM_REPO,
)
from pcs_core.registry import build_artifact_registry  # noqa: E402
from pcs_core.tool_use_validate import policy_hash_from_policy_id  # noqa: E402
from pcs_core.validate import validate_file  # noqa: E402

AGENT_REPO = "https://github.com/example/agent-runtime"
AGENT_COMMIT = "a111111111111111111111111111111111111111"
CERTIFYEDGE_COMMIT = "b222222222222222222222222222222222222222"
PF_COMMIT = "c333333333333333333333333333333333333333"
PCS_COMMIT = "d444444444444444444444444444444444444444"

TOOL_USE_WORKFLOW_ID = "agent_tool_use.safety_v0"
TOOL_USE_POLICY_ID = "policy-no-secret-exfiltration-v0"
TOOL_USE_CERT_ID = "cert-tool-use-safety-v0"
TOOL_USE_TRACE_ID = "trace-agent-safety-001"


def _with_digest(body: dict[str, Any]) -> dict[str, Any]:
    copy_body = dict(body)
    copy_body["signature_or_digest"] = PLACEHOLDER_DIGEST
    copy_body["signature_or_digest"] = canonical_hash(copy_body)
    return copy_body


def _violation(
    *,
    violation_id: str,
    event_id: str,
    violation_type: str,
    tool_name: str,
    policy_ref: str,
    explanation: str,
) -> dict[str, str]:
    return {
        "violation_id": violation_id,
        "event_id": event_id,
        "violation_type": violation_type,
        "tool_name": tool_name,
        "policy_ref": policy_ref,
        "explanation": explanation,
    }


def _trace_body() -> dict[str, Any]:
    policy_hash = policy_hash_from_policy_id(TOOL_USE_POLICY_ID)
    body: dict[str, Any] = {
        "schema_version": "v0",
        "trace_id": TOOL_USE_TRACE_ID,
        "workflow_id": TOOL_USE_WORKFLOW_ID,
        "agent_id": "agent-safety-conformance-001",
        "policy_id": TOOL_USE_POLICY_ID,
        "policy_hash": policy_hash,
        "started_at": "2026-05-18T00:00:00Z",
        "completed_at": "2026-05-18T00:00:05Z",
        "tool_calls": [
            {
                "event_id": "evt-001",
                "timestamp": "2026-05-18T00:00:01Z",
                "tool_name": "filesystem.read",
                "tool_category": "filesystem",
                "input_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "output_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "authorization_status": "authorized",
                "policy_refs": [TOOL_USE_POLICY_ID],
            },
        ],
        "trace_hash": PLACEHOLDER_DIGEST,
        "source_repo": AGENT_REPO,
        "source_commit": AGENT_COMMIT,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    without = dict(body)
    body["trace_hash"] = canonical_hash(without)
    return body


def _certificate_body(
    *,
    trace_hash: str,
    status: str = "CertificateChecked",
    violations: list[dict[str, str]] | None = None,
    policy_hash: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "v0",
        "certificate_id": TOOL_USE_CERT_ID,
        "trace_hash": trace_hash,
        "policy_hash": policy_hash or policy_hash_from_policy_id(TOOL_USE_POLICY_ID),
        "property_id": "agent_tool_use.policy_adherence",
        "checker": "certifyedge",
        "checker_version": "0.1.0",
        "status": status,
        "violations": violations if violations is not None else [],
        "source_repo": CERTIFYEDGE_REPO,
        "source_commit": CERTIFYEDGE_COMMIT,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }


def workflow_profile_labtrust() -> dict[str, Any]:
    body = {
        "schema_version": "v0",
        "workflow_id": "labtrust.qc_release_v0.1",
        "domain": "lab_science_simulation",
        "description": "Simulated hospital QC release chain using runtime receipts and trace certificates.",
        "runtime_artifacts": ["RuntimeReceipt.v0", "ScienceClaimBundle.v0"],
        "certificate_artifacts": ["TraceCertificate.v0"],
        "handoff_sequence": [
            "runtime_to_certificate",
            "certificate_to_bundle",
            "bundle_to_verifier",
            "signed_bundle_to_memory",
        ],
        "required_registry_entries": [
            "RuntimeReceipt.v0",
            "TraceCertificate.v0",
            "ScienceClaimBundle.v0",
            "VerificationResult.v0",
            "SignedScienceClaimBundle.v0",
            "ReleaseManifest.v0",
            "HandoffManifest.v0",
            "ReleaseChainValidationResult.v0",
            "WorkflowProfile.v0",
        ],
        "required_admission_profile": "labtrust_qc_release",
        "status_policy": {
            "policy_id": "pcs-v0.1-default-lifecycle",
            "description": "RuntimeObserved through ProofChecked with terminal Rejected and Stale.",
            "allowed_terminal_statuses": ["Rejected", "Stale", "Deprecated"],
            "forbidden_transitions": [
                {"from_status": "Rejected", "to_status": "ProofChecked"},
                {"from_status": "Stale", "to_status": "ProofChecked"},
            ],
        },
        "failure_modes": [
            "trace_hash_mismatch",
            "certificate_rejected",
            "verification_failed",
            "manifest_hash_mismatch",
        ],
        "limitations_notice": (
            "LabTrust QC release demonstrates a proof-carrying simulated workflow; "
            "not clinical certification."
        ),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


def workflow_profile_tool_use() -> dict[str, Any]:
    body = {
        "schema_version": "v0",
        "workflow_id": TOOL_USE_WORKFLOW_ID,
        "domain": "agent_tool_use",
        "description": "Proof-carrying tool-use safety workflow for agent traces.",
        "runtime_artifacts": ["ToolUseTrace.v0", "RuntimeReceipt.v0"],
        "certificate_artifacts": ["ToolUseCertificate.v0"],
        "handoff_sequence": [
            "runtime_to_certificate",
            "certificate_to_bundle",
            "bundle_to_verifier",
            "signed_bundle_to_memory",
        ],
        "required_registry_entries": [
            "ToolUseTrace.v0",
            "ToolUseCertificate.v0",
            "RuntimeReceipt.v0",
            "ScienceClaimBundle.v0",
            "VerificationResult.v0",
            "SignedScienceClaimBundle.v0",
            "ReleaseManifest.v0",
            "HandoffManifest.v0",
            "ReleaseChainValidationResult.v0",
            "WorkflowProfile.v0",
        ],
        "required_admission_profile": "agent_tool_use_safety",
        "status_policy": {
            "policy_id": "pcs-v0.1-tool-use-lifecycle",
            "description": "Tool traces require authorized calls before CertificateChecked export.",
            "allowed_terminal_statuses": ["Rejected", "Stale"],
            "forbidden_transitions": [
                {"from_status": "Rejected", "to_status": "ProofChecked"},
            ],
        },
        "failure_modes": [
            "unauthorized_tool_call",
            "missing_policy_hash",
            "tool_output_hash_mismatch",
            "unapproved_network_call",
            "unknown_authorization_status",
        ],
        "limitations_notice": (
            "This artifact is a proof-carrying tool-use simulation result. "
            "It is not a guarantee that a real deployed agent is safe."
        ),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    return _with_digest(body)


_PLACEHOLDER_COMMITS = {
    "a" * 40: AGENT_COMMIT,
    "b" * 40: CERTIFYEDGE_COMMIT,
    "c" * 40: PF_COMMIT,
    "d" * 40: PCS_COMMIT,
}


def _normalize_fixture_commits(obj: Any) -> None:
    if isinstance(obj, dict):
        commit = obj.get("source_commit")
        if isinstance(commit, str) and commit in _PLACEHOLDER_COMMITS:
            obj["source_commit"] = _PLACEHOLDER_COMMITS[commit]
        for value in obj.values():
            _normalize_fixture_commits(value)
    elif isinstance(obj, list):
        for item in obj:
            _normalize_fixture_commits(item)


def _patch_provenance(obj: Any, *, repo_substring: str, commit: str) -> None:
    if isinstance(obj, dict):
        repo = obj.get("source_repo")
        if isinstance(repo, str) and repo_substring.lower() in repo.lower():
            obj["source_commit"] = commit
        for value in obj.values():
            _patch_provenance(value, repo_substring=repo_substring, commit=commit)
    elif isinstance(obj, list):
        for item in obj:
            _patch_provenance(item, repo_substring=repo_substring, commit=commit)


def _adapt_science_bundle(cert_id: str, *, trace_hash: str) -> dict[str, Any]:
    src = examples_dir() / "science_claim_bundle.certified.valid.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    claim = data["claim_artifact"]
    claim["certificate_refs"] = [cert_id]
    claim["claim_text"] = (
        "The agent tool-use session satisfies the configured safety policy under stated assumptions."
    )
    claim["claim_kind"] = "temporal_claim"
    evidence = data["evidence_bundle"]
    evidence["certificate_refs"] = [cert_id]
    certs = data.get("certificates")
    if isinstance(certs, list) and certs and isinstance(certs[0], dict):
        certs[0]["certificate_id"] = cert_id
        certs[0]["trace_hash"] = trace_hash
        _patch_provenance(certs[0], repo_substring="certifyedge", commit=CERTIFYEDGE_COMMIT)
    receipts = data.get("runtime_receipts")
    if isinstance(receipts, list) and receipts and isinstance(receipts[0], dict):
        receipts[0]["trace_hash"] = trace_hash
        _patch_provenance(receipts[0], repo_substring="agent", commit=AGENT_COMMIT)
    data["verification_policy"] = {
        "policy_id": TOOL_USE_WORKFLOW_ID,
        "required_checks": ["schema-valid", "tool-trace-hash-alignment", "policy-hash-alignment"],
    }
    _patch_provenance(data, repo_substring="labtrust", commit=AGENT_COMMIT)
    _patch_provenance(data, repo_substring="certifyedge", commit=CERTIFYEDGE_COMMIT)
    return _with_digest(data)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    from pcs_core.release_fixtures import file_digest

    profiles = examples_dir() / "workflow_profiles"
    release = examples_dir() / "tool-use-release"
    invalid_root = examples_dir() / "tool-use-release-invalid"
    release.mkdir(parents=True, exist_ok=True)
    for stale_name in ("tool_use_trace.json", "tool_use_certificate.json"):
        stale_path = release / stale_name
        if stale_path.is_file():
            stale_path.unlink()

    _write_json(profiles / "labtrust_qc_release.valid.json", workflow_profile_labtrust())
    _write_json(profiles / "agent_tool_use_safety.valid.json", workflow_profile_tool_use())
    legacy_profile = profiles / "tool_use_safety.valid.json"
    if legacy_profile.is_file():
        legacy_profile.unlink()

    trace = _with_digest(_trace_body())
    cert = _with_digest(_certificate_body(trace_hash=str(trace["trace_hash"])))
    _write_json(release / "workflow_profile.v0.json", workflow_profile_tool_use())
    _write_json(release / "tool_use_trace.valid.json", trace)
    _write_json(release / "tool_use_certificate.valid.json", cert)
    runtime_receipt = json.loads(
        (examples_dir() / "runtime_receipt.valid.json").read_text(encoding="utf-8"),
    )
    runtime_receipt["trace_hash"] = trace["trace_hash"]
    runtime_receipt["source_commit"] = AGENT_COMMIT
    runtime_receipt["source_repo"] = AGENT_REPO
    _write_json(release / "runtime_receipt.json", _with_digest(runtime_receipt))
    _write_json(
        release / "science_claim_bundle.certified.json",
        _adapt_science_bundle(TOOL_USE_CERT_ID, trace_hash=str(trace["trace_hash"])),
    )

    for name in ("verification_result.json", "signed_science_claim_bundle.json"):
        src = examples_dir() / f"{name.replace('.json', '')}.valid.json"
        if src.is_file():
            doc = json.loads(src.read_text(encoding="utf-8"))
            _normalize_fixture_commits(doc)
            if name == "verification_result.json":
                verified = doc.get("verified_input")
                if isinstance(verified, dict):
                    verified["certificate_id"] = TOOL_USE_CERT_ID
            if name == "signed_science_claim_bundle.json":
                scb = doc.get("science_claim_bundle")
                if isinstance(scb, dict):
                    claim = scb.get("claim_artifact")
                    if isinstance(claim, dict):
                        claim["certificate_refs"] = [TOOL_USE_CERT_ID]
                    certs = scb.get("certificates")
                    if isinstance(certs, list) and certs and isinstance(certs[0], dict):
                        certs[0]["certificate_id"] = TOOL_USE_CERT_ID
                        certs[0]["trace_hash"] = trace["trace_hash"]
                    receipts = scb.get("runtime_receipts")
                    if isinstance(receipts, list) and receipts and isinstance(receipts[0], dict):
                        receipts[0]["trace_hash"] = trace["trace_hash"]
            _write_json(release / name, _with_digest(doc))

    certified = json.loads((release / "science_claim_bundle.certified.json").read_text(encoding="utf-8"))
    certified_digest = file_digest(
        (release / "science_claim_bundle.certified.json").read_bytes(),
    )
    vrf_path = release / "verification_result.json"
    if vrf_path.is_file():
        vrf = json.loads(vrf_path.read_text(encoding="utf-8"))
        verified = vrf.get("verified_input")
        if isinstance(verified, dict):
            verified["certificate_id"] = TOOL_USE_CERT_ID
            verified["bundle_hash"] = certified_digest
        _write_json(vrf_path, _with_digest(vrf))
    signed_path = release / "signed_science_claim_bundle.json"
    if signed_path.is_file():
        signed = json.loads(signed_path.read_text(encoding="utf-8"))
        signed["signed_input_bundle_hash"] = certified_digest
        _write_json(signed_path, _with_digest(signed))

    certified = json.loads((release / "science_claim_bundle.certified.json").read_text(encoding="utf-8"))
    signed = json.loads((release / "signed_science_claim_bundle.json").read_text(encoding="utf-8"))

    manifest_body: dict[str, Any] = {
        "schema_version": "v0",
        "release_id": "release-pcs-v0.1-tool-use-safety",
        "release_candidate": "pcs-v0.1-tool-use-safety-conformance",
        "generated_at": "2026-05-18T12:00:00Z",
        "validation_profile": TOOL_USE_WORKFLOW_ID,
        "workflow_profile_id": TOOL_USE_WORKFLOW_ID,
        "chain_root": {
            "trace_hash": trace["trace_hash"],
            "certificate_id": TOOL_USE_CERT_ID,
            "certified_bundle_hash": canonical_hash(certified),
            "signed_bundle_hash": canonical_hash(signed),
        },
        "release_chain_validation_result": {
            "path": "release_chain_validation_result.v0.json",
            "sha256": PLACEHOLDER_DIGEST,
        },
        "canonical_signed_bundle": {
            "path": "signed_science_claim_bundle.json",
            "sha256": canonical_hash(signed),
        },
        "canonical_claim_id": str(certified["claim_artifact"]["artifact_id"]),
        "limitations_notice": workflow_profile_tool_use()["limitations_notice"],
        "producer_repos": {
            "pcs_core": {"repo": PCS_CORE_REPO, "commit": PCS_COMMIT},
            "agent_runtime": {"repo": AGENT_REPO, "commit": AGENT_COMMIT},
            "certifyedge": {"repo": CERTIFYEDGE_REPO, "commit": CERTIFYEDGE_COMMIT},
            "provability_fabric": {"repo": PF_REPO, "commit": PF_COMMIT},
            "scientific_memory": {"repo": SM_REPO, "commit": PCS_COMMIT},
        },
        "artifacts": {},
        "release_status": "Validated",
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    runtime_receipt_doc = json.loads((release / "runtime_receipt.json").read_text(encoding="utf-8"))
    artifact_specs = {
        "tool_use_trace.valid.json": ("ToolUseTrace.v0", trace),
        "tool_use_certificate.valid.json": ("ToolUseCertificate.v0", cert),
        "runtime_receipt.json": ("RuntimeReceipt.v0", runtime_receipt_doc),
        "science_claim_bundle.certified.json": ("ScienceClaimBundle.v0", certified),
        "workflow_profile.v0.json": ("WorkflowProfile.v0", workflow_profile_tool_use()),
    }
    for filename, (artifact_type, doc) in artifact_specs.items():
        path = release / filename
        _write_json(path, doc)
        manifest_body["artifacts"][filename] = {
            "artifact_type": artifact_type,
            "schema": f"schemas/{artifact_type}.schema.json",
            "producer": "pcs-core",
            "source_repo": PCS_CORE_REPO,
            "source_commit": PCS_COMMIT,
            "sha256": file_digest(path.read_bytes()),
        }
    for filename, artifact_type in (
        ("verification_result.json", "VerificationResult.v0"),
        ("signed_science_claim_bundle.json", "SignedScienceClaimBundle.v0"),
    ):
        path = release / filename
        if path.is_file():
            manifest_body["artifacts"][filename] = {
                "artifact_type": artifact_type,
                "schema": f"schemas/{artifact_type}.schema.json",
                "producer": "Provability Fabric",
                "source_repo": PF_REPO,
                "source_commit": PF_COMMIT,
                "sha256": file_digest(path.read_bytes()),
            }

    validation: dict[str, Any] = {
        "schema_version": "v0",
        "validation_id": "validation-pcs-v0.1-tool-use-safety",
        "release_id": manifest_body["release_id"],
        "release_candidate": manifest_body["release_candidate"],
        "workflow_profile_id": TOOL_USE_WORKFLOW_ID,
        "validator": "pcs-core",
        "validator_version": "0.1.0",
        "checked_at": manifest_body["generated_at"],
        "status": "ProofChecked",
        "checks": [
            {
                "check_id": "tool_trace_hash_alignment",
                "description": "ToolUseCertificate trace_hash matches ToolUseTrace",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ToolUseCertificate.v0.tool_trace_hash_matches_certificate",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "tool_policy_hash_alignment",
                "description": "ToolUseCertificate policy_hash matches trace policy_id",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ToolUseCertificate.v0.policy_hash_matches_certificate",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "tool_certificate_status_checked",
                "description": "ToolUseCertificate status is CertificateChecked",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ToolUseCertificate.v0.certificate_status_checked_for_release",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "tool_no_unauthorized_calls",
                "description": "All tool calls are authorized for release",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ToolUseCertificate.v0.no_unauthorized_tool_calls",
                    "ToolUseTrace.v0.no_unknown_authorization_status",
                    "ToolUseTrace.v0.trace_hash_present",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "tool_certifyedge_commit",
                "description": "ToolUseCertificate source_commit matches release manifest",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ToolUseCertificate.v0.source_commit_matches_release_manifest",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "tool_certificate_signature_valid",
                "description": "ToolUseCertificate signature_or_digest is canonical",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ToolUseCertificate.v0.signature_or_digest_valid",
                ],
                "responsible_component": "CertifyEdge",
            },
            {
                "check_id": "release_manifest_integrity",
                "description": "Release manifest hashes and commit policy",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ReleaseManifest.v0.artifact_hashes_match_files",
                    "ReleaseManifest.v0.release_mode_commit_policy",
                ],
                "responsible_component": "pcs-core",
            },
            {
                "check_id": "runtime_receipt_commit",
                "description": "RuntimeReceipt trace hash and manifest commit alignment",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "RuntimeReceipt.v0.source_commit_matches_release_manifest",
                    "RuntimeReceipt.v0.trace_hash_present",
                ],
                "responsible_component": "AgentRuntime",
            },
            {
                "check_id": "science_claim_bundle_semantics",
                "description": "Certified science claim bundle structure",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "ScienceClaimBundle.v0.non_empty_runtime_receipts",
                    "ScienceClaimBundle.v0.certified_bundle_has_certificate_when_checked",
                ],
                "responsible_component": "LabTrust-Gym",
            },
            {
                "check_id": "verification_and_signed_bundle_hashes",
                "description": "Verification and signed bundle hash alignment",
                "status": "passed",
                "details": {},
                "registry_check_refs": [
                    "VerificationResult.v0.verified_input_bundle_hash_matches_certified",
                    "VerificationResult.v0.failed_checks_block_import_ready_status",
                    "SignedScienceClaimBundle.v0.signed_input_bundle_hash_matches_certified",
                ],
                "responsible_component": "Provability Fabric",
            },
        ],
        "artifacts_checked": len(manifest_body["artifacts"]),
        "failure_codes": [],
        "source_repo": PCS_CORE_REPO,
        "source_commit": PCS_COMMIT,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    from pcs_core.registry_semantics import (
        build_deferred_registry_checks,
        collect_chain_registry_refs,
        deferral_reason,
        enforcement_layer,
        lookup_registry_check,
    )
    from pcs_core.workflow_profiles import required_release_blocking_refs_for_profile

    validation["deferred_registry_checks"] = build_deferred_registry_checks(
        validation["checks"],
    )
    cited = collect_chain_registry_refs(validation["checks"])
    deferred_refs = {item["registry_ref"] for item in validation["deferred_registry_checks"]}
    for ref in sorted(required_release_blocking_refs_for_profile(TOOL_USE_WORKFLOW_ID) - cited - deferred_refs):
        found = lookup_registry_check(ref)
        if found is None:
            continue
        _artifact_type, check = found
        if enforcement_layer(check) == "release_chain":
            continue
        validation["deferred_registry_checks"].append(
            {
                "registry_ref": ref,
                "status": "deferred",
                "enforcement_location": enforcement_layer(check),
                "responsible_component": str(check.get("responsible_component", "pcs-core")),
                "reason": deferral_reason(str(check.get("check_id", ""))),
            },
        )
    validation["signature_or_digest"] = canonical_hash(validation)
    _write_json(release / "release_chain_validation_result.v0.json", validation)
    manifest_body["release_chain_validation_result"]["sha256"] = file_digest(
        (release / "release_chain_validation_result.v0.json").read_bytes(),
    )
    _write_json(release / "release_manifest.v0.json", _with_digest(manifest_body))

    def _invalid_unauthorized() -> tuple[dict[str, Any], dict[str, Any]]:
        tr = _with_digest(_trace_body())
        tr["tool_calls"] = [copy.deepcopy(tr["tool_calls"][0])]
        tr["tool_calls"][0]["authorization_status"] = "rejected"
        tr = _with_digest(tr)
        return tr, _with_digest(_certificate_body(trace_hash=str(tr["trace_hash"])))

    def _invalid_missing_policy() -> tuple[dict[str, Any], dict[str, Any]]:
        tr = _with_digest(_trace_body())
        tr.pop("policy_hash", None)
        tr = _with_digest(tr)
        cert = _certificate_body(trace_hash=str(tr["trace_hash"]))
        return tr, _with_digest(cert)

    def _invalid_mismatched_hash() -> tuple[dict[str, Any], dict[str, Any]]:
        tr = _with_digest(_trace_body())
        cert = _certificate_body(trace_hash="sha256:" + "e" * 64)
        return tr, _with_digest(cert)

    def _invalid_rejected_cert() -> tuple[dict[str, Any], dict[str, Any]]:
        tr = _with_digest(_trace_body())
        return tr, _with_digest(
            _certificate_body(
                trace_hash=str(tr["trace_hash"]),
                status="Rejected",
                violations=[
                    _violation(
                        violation_id="viol-001",
                        event_id="evt-001",
                        violation_type="unauthorized_tool_call",
                        tool_name="network.request",
                        policy_ref=TOOL_USE_POLICY_ID,
                        explanation="Network request not authorized by active policy.",
                    ),
                ],
            ),
        )

    def _invalid_policy_hash_mismatch() -> tuple[dict[str, Any], dict[str, Any]]:
        tr = _with_digest(_trace_body())
        cert = _certificate_body(trace_hash=str(tr["trace_hash"]))
        cert["policy_hash"] = "sha256:" + "c" * 64
        return tr, _with_digest(cert)

    def _invalid_unknown_auth() -> tuple[dict[str, Any], dict[str, Any]]:
        tr = _with_digest(_trace_body())
        tr["tool_calls"] = [copy.deepcopy(tr["tool_calls"][0])]
        tr["tool_calls"][0]["authorization_status"] = "unknown"
        tr = _with_digest(tr)
        return tr, _with_digest(_certificate_body(trace_hash=str(tr["trace_hash"])))

    builders: dict[str, Callable[[], tuple[dict[str, Any], dict[str, Any]]]] = {
        "unauthorized_tool_call": _invalid_unauthorized,
        "missing_policy_hash": _invalid_missing_policy,
        "trace_hash_mismatch": _invalid_mismatched_hash,
        "policy_hash_mismatch": _invalid_policy_hash_mismatch,
        "rejected_certificate": _invalid_rejected_cert,
        "unknown_authorization_status": _invalid_unknown_auth,
    }
    for case_name, builder in builders.items():
        tr_doc, cert_doc = builder()
        case_dir = invalid_root / case_name
        case_dir.mkdir(parents=True, exist_ok=True)
        for stale in case_dir.glob("*.json"):
            stale.unlink()
        _write_json(case_dir / "tool_use_trace.json", tr_doc)
        _write_json(case_dir / "tool_use_certificate.json", cert_doc)

    _write_json(examples_dir() / "artifact_registry.valid.json", build_artifact_registry())
    _write_json(examples_dir() / "tool_use_trace.valid.json", trace)
    _write_json(examples_dir() / "tool_use_certificate.valid.json", cert)

    from pcs_core.shared_hash_vectors import write_shared_vectors
    from pcs_core.semantic_check_execution import build_semantic_check_execution

    (examples_dir() / "semantic_check_execution.valid.json").write_text(
        json.dumps(build_semantic_check_execution(), indent=2) + "\n",
        encoding="utf-8",
    )
    write_shared_vectors(force=True)

    for path in sorted(profiles.glob("*.json")):
        validate_file(path)
    from pcs_core.tool_use_release_chain import TOOL_USE_MANIFEST_ARTIFACTS

    sm_report = {
        "allow_legacy": False,
        "bundle_shape": "pcs_core",
        "claim_id": manifest_body["canonical_claim_id"],
        "imported_at": manifest_body["generated_at"],
        "render_path": f"/pcs/workflows/{TOOL_USE_WORKFLOW_ID}/claims/{manifest_body['canonical_claim_id']}",
        "workflow_profile_id": TOOL_USE_WORKFLOW_ID,
        "workflow_profile_render_path": f"/pcs/workflows/{TOOL_USE_WORKFLOW_ID}/profile",
        "scientific_memory_commit": PCS_COMMIT,
        "source_bundle_path": "signed_science_claim_bundle.json",
        "stale_artifacts": [],
        "strict": True,
        "verification_status": "passed",
        "warnings": [],
        "source_commit": PCS_COMMIT,
        "source_repo": SM_REPO,
        "release_id": manifest_body["release_id"],
        "release_candidate": manifest_body["release_candidate"],
        "release_manifest_path": "release_manifest.v0.json",
        "validation_profile": TOOL_USE_WORKFLOW_ID,
        "release_chain_validation_id": validation["validation_id"],
        "release_chain_validation_status": validation["status"],
        "release_chain_validator": "pcs-core",
        "release_chain_checked_at": validation["checked_at"],
        "release_manifest_hash": canonical_hash(manifest_body),
    }
    _write_json(release / "scientific_memory_import_report.json", sm_report)

    trace_digest = file_digest((release / "tool_use_trace.valid.json").read_bytes())
    cert_digest = file_digest((release / "tool_use_certificate.valid.json").read_bytes())
    receipt_digest = file_digest((release / "runtime_receipt.json").read_bytes())
    certified_digest = file_digest((release / "science_claim_bundle.certified.json").read_bytes())

    handoff_to_certifyedge = _with_digest(
        {
            "schema_version": "v0",
            "handoff_id": "handoff-tool-use-runtime-to-certifyedge",
            "handoff_kind": "runtime_to_certificate",
            "from_component": "agent-tool-use demo producer",
            "to_component": "CertifyEdge",
            "created_at": manifest_body["generated_at"],
            "source_repo": AGENT_REPO,
            "source_commit": AGENT_COMMIT,
            "input_artifacts": {
                "tool_use_trace.valid.json": {
                    "artifact_type": "ToolUseTrace.v0",
                    "sha256": trace_digest,
                },
                "runtime_receipt.json": {
                    "artifact_type": "RuntimeReceipt.v0",
                    "sha256": receipt_digest,
                },
            },
            "expected_outputs": {
                "tool_use_certificate.valid.json": {"artifact_type": "ToolUseCertificate.v0"},
            },
            "invariants": {"trace_hash": trace["trace_hash"]},
            "status": "Validated",
            "signature_or_digest": PLACEHOLDER_DIGEST,
        },
    )
    _write_json(release / "handoff_to_certifyedge.json", handoff_to_certifyedge)
    _write_json(release / "handoff_manifest.runtime_to_certificate.v0.json", handoff_to_certifyedge)

    handoff_to_pf = _with_digest(
        {
            "schema_version": "v0",
            "handoff_id": "handoff-tool-use-to-pf",
            "handoff_kind": "bundle_to_verifier",
            "from_component": "CertifyEdge",
            "to_component": "Provability Fabric",
            "created_at": manifest_body["generated_at"],
            "source_repo": CERTIFYEDGE_REPO,
            "source_commit": CERTIFYEDGE_COMMIT,
            "input_artifacts": {
                "science_claim_bundle.certified.json": {
                    "artifact_type": "ScienceClaimBundle.v0",
                    "sha256": certified_digest,
                },
            },
            "expected_outputs": {
                "verification_result.json": {"artifact_type": "VerificationResult.v0"},
                "signed_science_claim_bundle.json": {
                    "artifact_type": "SignedScienceClaimBundle.v0",
                },
            },
            "invariants": {
                "certificate_id": TOOL_USE_CERT_ID,
                "trace_hash": trace["trace_hash"],
                "certified_bundle_hash": certified_digest,
            },
            "status": "Validated",
            "signature_or_digest": PLACEHOLDER_DIGEST,
        },
    )
    _write_json(release / "handoff_to_pf.json", handoff_to_pf)
    _write_json(release / "handoff_manifest.bundle_to_verifier.v0.json", handoff_to_pf)

    handoff_cert_to_bundle = _with_digest(
        {
            "schema_version": "v0",
            "handoff_id": "handoff-tool-use-certificate-to-bundle",
            "handoff_kind": "certificate_to_bundle",
            "from_component": "CertifyEdge",
            "to_component": "agent-tool-use demo producer",
            "created_at": manifest_body["generated_at"],
            "source_repo": CERTIFYEDGE_REPO,
            "source_commit": CERTIFYEDGE_COMMIT,
            "input_artifacts": {
                "tool_use_certificate.valid.json": {
                    "artifact_type": "ToolUseCertificate.v0",
                    "sha256": cert_digest,
                },
            },
            "expected_outputs": {
                "science_claim_bundle.certified.json": {
                    "artifact_type": "ScienceClaimBundle.v0",
                },
            },
            "invariants": {
                "certificate_id": TOOL_USE_CERT_ID,
                "trace_hash": trace["trace_hash"],
            },
            "status": "Validated",
            "signature_or_digest": PLACEHOLDER_DIGEST,
        },
    )
    _write_json(release / "handoff_manifest.certificate_to_bundle.v0.json", handoff_cert_to_bundle)

    signed_digest = file_digest((release / "signed_science_claim_bundle.json").read_bytes())
    handoff_signed_to_memory = _with_digest(
        {
            "schema_version": "v0",
            "handoff_id": "handoff-tool-use-signed-bundle-to-memory",
            "handoff_kind": "signed_bundle_to_memory",
            "from_component": "Provability Fabric",
            "to_component": "Scientific Memory",
            "created_at": manifest_body["generated_at"],
            "source_repo": PF_REPO,
            "source_commit": PF_COMMIT,
            "input_artifacts": {
                "signed_science_claim_bundle.json": {
                    "artifact_type": "SignedScienceClaimBundle.v0",
                    "sha256": signed_digest,
                },
            },
            "expected_outputs": {
                "scientific_memory_import_report.json": {
                    "artifact_type": "ScientificMemory.ImportReport.v0",
                },
            },
            "invariants": {
                "workflow_profile_id": TOOL_USE_WORKFLOW_ID,
                "claim_id": manifest_body["canonical_claim_id"],
            },
            "status": "Validated",
            "signature_or_digest": PLACEHOLDER_DIGEST,
        },
    )
    _write_json(
        release / "handoff_manifest.signed_bundle_to_memory.v0.json",
        handoff_signed_to_memory,
    )

    legacy_manifest = {
        "schema_version": "v0",
        "release_candidate": manifest_body["release_candidate"],
        "generated_at": manifest_body["generated_at"],
        "workflow_profile_id": TOOL_USE_WORKFLOW_ID,
        "pcs_core_commit": PCS_COMMIT,
        "agent_runtime_commit": AGENT_COMMIT,
        "certifyedge_commit": CERTIFYEDGE_COMMIT,
        "provability_fabric_commit": PF_COMMIT,
        "scientific_memory_commit": PCS_COMMIT,
        "artifacts": {
            name: file_digest((release / name).read_bytes())
            for name in TOOL_USE_MANIFEST_ARTIFACTS
            if (release / name).is_file()
        },
    }
    _write_json(release / "RELEASE_FIXTURE_MANIFEST.json", legacy_manifest)

    for rel in (
        "tool_use_trace.valid.json",
        "tool_use_certificate.valid.json",
        "workflow_profile.v0.json",
        "release_manifest.v0.json",
        "release_chain_validation_result.v0.json",
        "handoff_to_certifyedge.json",
        "handoff_to_pf.json",
    ):
        validate_file(release / rel)
    validate_file(examples_dir() / "artifact_registry.valid.json")
    print(f"Wrote tool-use fixtures under {release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
