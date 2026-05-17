"""Atomic PCS v0.1 LabTrust release-chain validation."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pcs_core.release_fixtures import (
    COMMIT_KEYS,
    LABTRUST_SOURCE_REPO,
    CERTIFYEDGE_SOURCE_REPO,
    PF_SOURCE_REPO,
    SM_SOURCE_REPO,
    MANIFEST_ARTIFACTS,
    MANIFEST_NAME,
    RELEASE_PCS_ARTIFACTS,
    _load_json,
    _scan_forbidden_values,
    _validate_trace_hash_alignment,
    file_digest,
    is_placeholder_commit,
)
from pcs_core.validate import ValidationError, validate_file

SIGNATURE_FIELD = "signature_or_digest"


@dataclass(frozen=True)
class ReleaseChainIssue:
    code: str
    message: str

    def format(self) -> str:
        return f"{self.code}: {self.message}"


def _issue(code: str, message: str) -> ReleaseChainIssue:
    return ReleaseChainIssue(code=code, message=message)


def _first_certificate_id(bundle: dict[str, Any]) -> str | None:
    certs = bundle.get("certificates")
    if not isinstance(certs, list) or not certs:
        return None
    first = certs[0]
    if isinstance(first, dict):
        cid = first.get("certificate_id")
        return cid if isinstance(cid, str) else None
    return None


def _certificate_ref_ids(bundle: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("claim_artifact", "evidence_bundle"):
        part = bundle.get(key)
        if not isinstance(part, dict):
            continue
        certificate_refs = part.get("certificate_refs")
        if isinstance(certificate_refs, list):
            refs.extend(ref for ref in certificate_refs if isinstance(ref, str))
    return refs


def _verified_input_certificate_id(vr: dict[str, Any]) -> str | None:
    verified = vr.get("verified_input")
    if isinstance(verified, dict):
        cid = verified.get("certificate_id")
        return cid if isinstance(cid, str) else None
    return None


def _iter_provenance_pairs(obj: Any) -> Iterator[tuple[str, str]]:
    if isinstance(obj, dict):
        repo = obj.get("source_repo")
        commit = obj.get("source_commit")
        if isinstance(repo, str) and isinstance(commit, str):
            yield repo, commit
        for value in obj.values():
            yield from _iter_provenance_pairs(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_provenance_pairs(item)


def _repo_matches(repo: str, expected_repo: str) -> bool:
    return expected_repo.lower() in repo.lower()


def validate_release_chain(directory: Path) -> list[ReleaseChainIssue]:
    """Validate a complete release directory for single-run atomic consistency."""
    issues: list[ReleaseChainIssue] = []
    base = directory.resolve()

    manifest_path = base / MANIFEST_NAME
    if not manifest_path.is_file():
        issues.append(_issue("missing_manifest", f"{MANIFEST_NAME} not found in {base}"))
        return issues

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(_issue("invalid_manifest", f"manifest JSON parse error: {exc}"))
        return issues

    if not isinstance(manifest, dict):
        issues.append(_issue("invalid_manifest", "manifest root must be a JSON object"))
        return issues

    commits = {key: manifest.get(key) for key in COMMIT_KEYS}
    for key in COMMIT_KEYS:
        commit = commits[key]
        if not isinstance(commit, str) or len(commit) != 40:
            issues.append(_issue("manifest_commit_mismatch", f"manifest missing or invalid {key}"))
        elif is_placeholder_commit(commit):
            issues.append(
                _issue(
                    "manifest_commit_mismatch",
                    f"manifest {key} uses placeholder provenance: {commit}",
                ),
            )

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        issues.append(_issue("invalid_manifest", "manifest artifacts must be an object"))
        return issues

    if set(artifacts) != set(MANIFEST_ARTIFACTS):
        missing = sorted(set(MANIFEST_ARTIFACTS) - set(artifacts))
        extra = sorted(set(artifacts) - set(MANIFEST_ARTIFACTS))
        if missing:
            issues.append(_issue("invalid_manifest", f"manifest artifacts missing keys: {missing}"))
        if extra:
            issues.append(_issue("invalid_manifest", f"manifest artifacts unexpected keys: {extra}"))

    for name in MANIFEST_ARTIFACTS:
        path = base / name
        if not path.is_file():
            issues.append(_issue("missing_artifact", f"missing artifact file {name}"))
            continue
        expected = artifacts.get(name)
        actual = file_digest(path.read_bytes())
        if expected != actual:
            issues.append(
                _issue(
                    "manifest_hash_mismatch",
                    f"{name}: manifest digest mismatch (expected {expected}, got {actual})",
                ),
            )

    scan_errors: list[str] = []
    for name in MANIFEST_ARTIFACTS:
        path = base / name
        if not path.is_file():
            continue
        doc = _load_json(path)
        if doc is None:
            issues.append(_issue("invalid_artifact", f"{name}: invalid JSON"))
            continue
        _scan_forbidden_values(doc, label=name, errors=scan_errors)
    for msg in scan_errors:
        if "placeholder" in msg:
            issues.append(_issue("placeholder_commit_detected", msg))
        elif "local_dev" in msg:
            issues.append(_issue("placeholder_commit_detected", msg))
        else:
            issues.append(_issue("invalid_artifact", msg))

    trace_errors: list[str] = []
    _validate_trace_hash_alignment(base, trace_errors)
    for msg in trace_errors:
        issues.append(_issue("invalid_artifact", msg))

    for name in RELEASE_PCS_ARTIFACTS:
        path = base / name
        if not path.is_file():
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            issues.append(_issue("invalid_artifact", f"{name}: pcs validate failed: {exc}"))

    lt_commit = commits.get("labtrust_gym_commit")
    ce_commit = commits.get("certifyedge_commit")
    pf_commit = commits.get("provability_fabric_commit")
    sm_commit = commits.get("scientific_memory_commit")

    receipt = _load_json(base / "runtime_receipt.json")
    pending = _load_json(base / "science_claim_bundle.pending.json")
    certified = _load_json(base / "science_claim_bundle.certified.json")
    verification = _load_json(base / "verification_result.json")
    signed = _load_json(base / "signed_science_claim_bundle.json")
    trace_cert = _load_json(base / "trace_certificate.json")
    sm_report = _load_json(base / "scientific_memory_import_report.json")

    if isinstance(lt_commit, str):
        if receipt and receipt.get("source_commit") != lt_commit:
            issues.append(
                _issue(
                    "labtrust_commit_mismatch",
                    f"runtime_receipt.source_commit {receipt.get('source_commit')!r} "
                    f"!= manifest.labtrust_gym_commit {lt_commit}",
                ),
            )
        for label, doc in (
            ("science_claim_bundle.pending.json", pending),
            ("science_claim_bundle.certified.json", certified),
            ("signed_science_claim_bundle.json", signed),
        ):
            if not isinstance(doc, dict):
                continue
            for repo, commit in _iter_provenance_pairs(doc):
                if _repo_matches(repo, LABTRUST_SOURCE_REPO) and commit != lt_commit:
                    issues.append(
                        _issue(
                            "labtrust_commit_mismatch",
                            f"{label}: LabTrust source_commit {commit} "
                            f"!= manifest.labtrust_gym_commit {lt_commit}",
                        ),
                    )

    if isinstance(ce_commit, str):
        if trace_cert and trace_cert.get("source_commit") != ce_commit:
            issues.append(
                _issue(
                    "certifyedge_commit_mismatch",
                    f"trace_certificate.source_commit {trace_cert.get('source_commit')!r} "
                    f"!= manifest.certifyedge_commit {ce_commit}",
                ),
            )
        for label, doc in (
            ("science_claim_bundle.certified.json", certified),
            ("signed_science_claim_bundle.json", signed),
        ):
            if not isinstance(doc, dict):
                continue
            for repo, commit in _iter_provenance_pairs(doc):
                if _repo_matches(repo, CERTIFYEDGE_SOURCE_REPO) and commit != ce_commit:
                    issues.append(
                        _issue(
                            "certifyedge_commit_mismatch",
                            f"{label}: CertifyEdge source_commit {commit} "
                            f"!= manifest.certifyedge_commit {ce_commit}",
                        ),
                    )

    if isinstance(pf_commit, str):
        if verification and verification.get("source_commit") != pf_commit:
            issues.append(
                _issue(
                    "pf_commit_mismatch",
                    f"verification_result.source_commit {verification.get('source_commit')!r} "
                    f"!= manifest.provability_fabric_commit {pf_commit}",
                ),
            )
        if signed and signed.get("source_commit") != pf_commit:
            issues.append(
                _issue(
                    "pf_commit_mismatch",
                    f"signed_science_claim_bundle.source_commit {signed.get('source_commit')!r} "
                    f"!= manifest.provability_fabric_commit {pf_commit}",
                ),
            )
        for label, doc in (
            ("verification_result.json", verification),
            ("signed_science_claim_bundle.json", signed),
        ):
            if not isinstance(doc, dict):
                continue
            for repo, commit in _iter_provenance_pairs(doc):
                if _repo_matches(repo, PF_SOURCE_REPO) and commit != pf_commit:
                    issues.append(
                        _issue(
                            "pf_commit_mismatch",
                            f"{label}: PF source_commit {commit} "
                            f"!= manifest.provability_fabric_commit {pf_commit}",
                        ),
                    )

    if isinstance(sm_commit, str) and sm_report:
        sm_src = sm_report.get("source_commit")
        sm_pin = sm_report.get("scientific_memory_commit")
        if sm_src != sm_commit:
            issues.append(
                _issue(
                    "scientific_memory_commit_mismatch",
                    f"scientific_memory_import_report.source_commit {sm_src!r} "
                    f"!= manifest.scientific_memory_commit {sm_commit}",
                ),
            )
        if sm_pin is not None and sm_pin != sm_commit:
            issues.append(
                _issue(
                    "scientific_memory_commit_mismatch",
                    f"scientific_memory_import_report.scientific_memory_commit {sm_pin!r} "
                    f"!= manifest.scientific_memory_commit {sm_commit}",
                ),
            )
        if sm_report.get("verification_status") != "passed":
            issues.append(
                _issue(
                    "scientific_memory_import_failed",
                    "scientific_memory_import_report.verification_status must be passed",
                ),
            )

    certified_cert_id = _first_certificate_id(certified) if certified else None
    trace_cert_id = trace_cert.get("certificate_id") if trace_cert else None
    vr_cert_id = _verified_input_certificate_id(verification) if verification else None
    signed_scb = signed.get("science_claim_bundle") if signed else None
    signed_cert_id = _first_certificate_id(signed_scb) if isinstance(signed_scb, dict) else None

    cert_ids = {
        cid
        for cid in (certified_cert_id, trace_cert_id, vr_cert_id, signed_cert_id)
        if isinstance(cid, str)
    }
    if len(cert_ids) > 1:
        issues.append(
            _issue(
                "certificate_id_mismatch",
                "certificate_id mismatch across trace_certificate, certified bundle, "
                f"verification_result.verified_input, and signed bundle ({cert_ids})",
            ),
        )
    elif certified_cert_id and certified:
        if trace_cert_id and trace_cert_id != certified_cert_id:
            issues.append(
                _issue(
                    "certificate_id_mismatch",
                    f"trace_certificate.certificate_id {trace_cert_id} != certified {certified_cert_id}",
                ),
            )
        if vr_cert_id and vr_cert_id != certified_cert_id:
            issues.append(
                _issue(
                    "certificate_id_mismatch",
                    "verification_result.verified_input.certificate_id "
                    f"{vr_cert_id} != certified {certified_cert_id}",
                ),
            )
        if signed_cert_id and signed_cert_id != certified_cert_id:
            issues.append(
                _issue(
                    "certificate_id_mismatch",
                    "signed.science_claim_bundle certificate_id "
                    f"{signed_cert_id} != certified {certified_cert_id}",
                ),
            )
        for ref_id in _certificate_ref_ids(certified):
            if ref_id != certified_cert_id:
                issues.append(
                    _issue(
                        "certificate_id_mismatch",
                        f"certified bundle certificate_refs entry {ref_id!r} "
                        f"!= {certified_cert_id}",
                    ),
                )
        if signed:
            scb = signed.get("science_claim_bundle")
            if isinstance(scb, dict):
                for ref_id in _certificate_ref_ids(scb):
                    if ref_id != certified_cert_id:
                        issues.append(
                            _issue(
                                "certificate_id_mismatch",
                                f"signed bundle certificate_refs entry {ref_id!r} "
                                f"!= {certified_cert_id}",
                            ),
                        )

    if verification and verification.get("status") != "ProofChecked":
        issues.append(
            _issue(
                "invalid_artifact",
                "verification_result.status must be ProofChecked",
            ),
        )
    if signed:
        embedded_vr = signed.get("verification_result")
        if isinstance(embedded_vr, dict) and embedded_vr.get("status") != "ProofChecked":
            issues.append(
                _issue(
                    "invalid_artifact",
                    "signed.verification_result.status must be ProofChecked",
                ),
            )

    if not verification or not verification.get("verified_input"):
        issues.append(
            _issue(
                "invalid_artifact",
                "verification_result.verified_input is required for release chain fixtures",
            ),
        )

    certified_hash = artifacts.get("science_claim_bundle.certified.json")
    if certified_hash and verification:
        verified = verification.get("verified_input")
        if isinstance(verified, dict):
            bundle_hash = verified.get("bundle_hash")
            if not bundle_hash:
                issues.append(
                    _issue(
                        "verified_input_hash_mismatch",
                        "verification_result.verified_input.bundle_hash is required",
                    ),
                )
            elif bundle_hash != certified_hash:
                issues.append(
                    _issue(
                        "verified_input_hash_mismatch",
                        f"verified_input.bundle_hash {bundle_hash} != manifest certified bundle hash "
                        f"{certified_hash}",
                    ),
                )
    if signed and certified_hash:
        signed_hash = signed.get("signed_input_bundle_hash")
        if not signed_hash:
            issues.append(
                _issue(
                    "signed_input_hash_mismatch",
                    "signed_science_claim_bundle.signed_input_bundle_hash is required",
                ),
            )
        elif signed_hash != certified_hash:
            issues.append(
                _issue(
                    "signed_input_hash_mismatch",
                    f"signed_input_bundle_hash {signed_hash} != manifest certified bundle hash "
                    f"{certified_hash}",
                ),
            )

    if trace_cert and trace_cert.get("status") != "CertificateChecked":
        issues.append(
            _issue(
                "invalid_artifact",
                "trace_certificate.status must be CertificateChecked",
            ),
        )

    return issues


def validate_release_chain_messages(directory: Path) -> list[str]:
    return [issue.format() for issue in validate_release_chain(directory)]
