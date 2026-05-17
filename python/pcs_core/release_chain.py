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


def _first_certificate_ref(bundle: dict[str, Any], part_key: str) -> str | None:
    part = bundle.get(part_key)
    if not isinstance(part, dict):
        return None
    certificate_refs = part.get("certificate_refs")
    if not isinstance(certificate_refs, list) or not certificate_refs:
        return None
    first = certificate_refs[0]
    return first if isinstance(first, str) else None


def _expect_certificate_id(
    issues: list[ReleaseChainIssue],
    *,
    expected: str,
    actual: str | None,
    label: str,
) -> None:
    if actual is None:
        issues.append(
            _issue("certificate_id_mismatch", f"{label}: certificate ID is required"),
        )
    elif actual != expected:
        issues.append(
            _issue(
                "certificate_id_mismatch",
                f"{label}: expected {expected!r}, got {actual!r}",
            ),
        )


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
        issues.append(_issue("manifest_missing", f"{MANIFEST_NAME} not found in {base}"))
        return issues

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(_issue("schema_validation_failed", f"manifest JSON parse error: {exc}"))
        return issues

    if not isinstance(manifest, dict):
        issues.append(_issue("schema_validation_failed", "manifest root must be a JSON object"))
        return issues

    commits = {key: manifest.get(key) for key in COMMIT_KEYS}
    for key in COMMIT_KEYS:
        commit = commits[key]
        if not isinstance(commit, str) or len(commit) != 40:
            issues.append(_issue("schema_validation_failed", f"manifest missing or invalid {key}"))
        elif is_placeholder_commit(commit) or commit == "0" * 40:
            issues.append(
                _issue(
                    "placeholder_commit_detected",
                    f"manifest {key} uses forbidden provenance: {commit}",
                ),
            )

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        issues.append(_issue("schema_validation_failed", "manifest artifacts must be an object"))
        return issues

    if set(artifacts) != set(MANIFEST_ARTIFACTS):
        missing = sorted(set(MANIFEST_ARTIFACTS) - set(artifacts))
        extra = sorted(set(artifacts) - set(MANIFEST_ARTIFACTS))
        if missing:
            issues.append(_issue("schema_validation_failed", f"manifest artifacts missing keys: {missing}"))
        if extra:
            issues.append(_issue("schema_validation_failed", f"manifest artifacts unexpected keys: {extra}"))

    for name in MANIFEST_ARTIFACTS:
        path = base / name
        if not path.is_file():
            issues.append(_issue("artifact_missing", f"missing artifact file {name}"))
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
            issues.append(_issue("schema_validation_failed", f"{name}: invalid JSON"))
            continue
        _scan_forbidden_values(doc, label=name, errors=scan_errors)
    for msg in scan_errors:
        if "placeholder" in msg or "zero" in msg or "local_dev" in msg:
            issues.append(_issue("placeholder_commit_detected", msg))
        else:
            issues.append(_issue("schema_validation_failed", msg))

    trace_errors: list[str] = []
    _validate_trace_hash_alignment(base, trace_errors)
    for msg in trace_errors:
        issues.append(_issue("trace_hash_mismatch", msg))

    for name in RELEASE_PCS_ARTIFACTS:
        path = base / name
        if not path.is_file():
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            issues.append(_issue("schema_validation_failed", f"{name}: pcs validate failed: {exc}"))

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
        if signed:
            signed_scb = signed.get("science_claim_bundle")
            if isinstance(signed_scb, dict):
                for repo, commit in _iter_provenance_pairs(signed_scb):
                    if _repo_matches(repo, LABTRUST_SOURCE_REPO) and commit != lt_commit:
                        issues.append(
                            _issue(
                                "labtrust_commit_mismatch",
                                "signed_science_claim_bundle.science_claim_bundle: "
                                f"LabTrust source_commit {commit} "
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
        if sm_report.get("strict") is not True:
            issues.append(
                _issue(
                    "scientific_memory_import_failed",
                    "scientific_memory_import_report.strict must be true",
                ),
            )
        if sm_report.get("allow_legacy") is not False:
            issues.append(
                _issue(
                    "legacy_import_detected",
                    "scientific_memory_import_report.allow_legacy must be false",
                ),
            )
        if sm_report.get("bundle_shape") != "pcs_core":
            issues.append(
                _issue(
                    "legacy_import_detected",
                    "scientific_memory_import_report.bundle_shape must be pcs_core "
                    f"(got {sm_report.get('bundle_shape')!r})",
                ),
            )

    certified_cert_id = _first_certificate_id(certified) if certified else None
    signed_scb = signed.get("science_claim_bundle") if signed else None

    if certified_cert_id and certified:
        _expect_certificate_id(
            issues,
            expected=certified_cert_id,
            actual=trace_cert.get("certificate_id") if trace_cert else None,
            label="trace_certificate.certificate_id",
        )
        _expect_certificate_id(
            issues,
            expected=certified_cert_id,
            actual=_first_certificate_ref(certified, "claim_artifact"),
            label="science_claim_bundle.certified.claim_artifact.certificate_refs[0]",
        )
        _expect_certificate_id(
            issues,
            expected=certified_cert_id,
            actual=_first_certificate_ref(certified, "evidence_bundle"),
            label="science_claim_bundle.certified.evidence_bundle.certificate_refs[0]",
        )
        _expect_certificate_id(
            issues,
            expected=certified_cert_id,
            actual=_verified_input_certificate_id(verification) if verification else None,
            label="verification_result.verified_input.certificate_id",
        )
        if isinstance(signed_scb, dict):
            _expect_certificate_id(
                issues,
                expected=certified_cert_id,
                actual=_first_certificate_id(signed_scb),
                label="signed_science_claim_bundle.science_claim_bundle.certificates[0].certificate_id",
            )

    if verification and verification.get("status") != "ProofChecked":
        issues.append(
            _issue(
                "schema_validation_failed",
                "verification_result.status must be ProofChecked",
            ),
        )
    if signed:
        embedded_vr = signed.get("verification_result")
        if isinstance(embedded_vr, dict) and embedded_vr.get("status") != "ProofChecked":
            issues.append(
                _issue(
                    "schema_validation_failed",
                    "signed.verification_result.status must be ProofChecked",
                ),
            )

    if not verification or not verification.get("verified_input"):
        issues.append(
            _issue(
                "schema_validation_failed",
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
                "schema_validation_failed",
                "trace_certificate.status must be CertificateChecked",
            ),
        )

    return issues


def validate_release_chain_messages(directory: Path) -> list[str]:
    return [issue.format() for issue in validate_release_chain(directory)]
