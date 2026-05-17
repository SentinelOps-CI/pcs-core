"""Atomic PCS v0.1 LabTrust release-chain validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pcs_core.release_fixtures import (
    COMMIT_KEYS,
    MANIFEST_ARTIFACTS,
    MANIFEST_NAME,
    RELEASE_PCS_ARTIFACTS,
    _load_json,
    _scan_forbidden_values,
    _validate_nested_provenance,
    _validate_trace_hash_alignment,
    file_digest,
    is_placeholder_commit,
    manifest_commit_key,
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


def _vr_certificate_refs(vr: dict[str, Any]) -> list[str]:
    checks = vr.get("checks")
    if not isinstance(checks, list):
        return []
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("check_id") != "evidence_refs_complete":
            continue
        details = check.get("details")
        if not isinstance(details, dict):
            return []
        refs = details.get("certificate_refs")
        if isinstance(refs, list):
            return [r for r in refs if isinstance(r, str)]
    return []


def _strip_signatures(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: _strip_signatures(v)
            for k, v in value.items()
            if k != SIGNATURE_FIELD
        }
    if isinstance(value, list):
        return [_strip_signatures(item) for item in value]
    return value


def _json_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return _strip_signatures(a) == _strip_signatures(b)


def validate_release_chain(directory: Path) -> list[ReleaseChainIssue]:
    """Validate a complete release-run directory for single-run atomic consistency."""
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

    string_errors: list[str] = []
    for name in MANIFEST_ARTIFACTS:
        path = base / name
        if not path.is_file():
            continue
        doc = _load_json(path)
        if doc is None:
            issues.append(_issue("invalid_artifact", f"{name}: invalid JSON"))
            continue
        _scan_forbidden_values(doc, label=name, errors=string_errors)
        repo = doc.get("source_repo")
        commit = doc.get("source_commit")
        if isinstance(repo, str) and isinstance(commit, str):
            key = manifest_commit_key(repo)
            if key and isinstance(commits.get(key), str) and commits[key] != commit:
                issues.append(
                    _issue(
                        "manifest_commit_mismatch",
                        f"{name}: source_commit {commit} != manifest {key} ({commits[key]})",
                    ),
                )

    for msg in string_errors:
        if "placeholder" in msg:
            issues.append(_issue("manifest_commit_mismatch", msg))
        elif "local_dev" in msg:
            issues.append(_issue("invalid_artifact", msg))
        else:
            issues.append(_issue("invalid_artifact", msg))

    nested_errors: list[str] = []
    _validate_nested_provenance(base, manifest, nested_errors)
    for msg in nested_errors:
        if "source_commit expected" in msg or "source_repo expected" in msg:
            if "certifyedge" in msg.lower() or "certificates" in msg:
                issues.append(_issue("mixed_run_labtrust_commit", msg))
            elif "provability" in msg.lower() or "verification" in msg:
                issues.append(_issue("mixed_run_pf_verification_result", msg))
            else:
                issues.append(_issue("mixed_run_labtrust_commit", msg))
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

    trace_cert = _load_json(base / "trace_certificate.json")
    certified = _load_json(base / "science_claim_bundle.certified.json")
    verification = _load_json(base / "verification_result.json")
    signed = _load_json(base / "signed_science_claim_bundle.json")
    sm_report = _load_json(base / "scientific_memory_import_report.json")

    cert_ids: dict[str, str | None] = {
        "trace_certificate.json": trace_cert.get("certificate_id") if trace_cert else None,
        "science_claim_bundle.certified.json": _first_certificate_id(certified) if certified else None,
    }

    if trace_cert and trace_cert.get("status") != "CertificateChecked":
        issues.append(
            _issue(
                "invalid_artifact",
                "trace_certificate.status must be CertificateChecked",
            ),
        )

    if verification:
        if verification.get("status") != "ProofChecked":
            issues.append(
                _issue(
                    "mixed_run_pf_verification_result",
                    "verification_result.status must be ProofChecked",
                ),
            )
        if certified and verification.get("bundle_id") != certified.get("bundle_id"):
            issues.append(
                _issue(
                    "mixed_run_pf_verification_result",
                    "verification_result.bundle_id does not match certified bundle_id",
                ),
            )

    vr_refs = _vr_certificate_refs(verification) if verification else []
    if vr_refs:
        cert_ids["verification_result.json"] = vr_refs[0]

    if signed:
        scb = signed.get("science_claim_bundle")
        if isinstance(scb, dict):
            cert_ids["signed_science_claim_bundle.json"] = _first_certificate_id(scb)
        embedded_vr = signed.get("verification_result")
        if isinstance(embedded_vr, dict):
            if embedded_vr.get("status") != "ProofChecked":
                issues.append(
                    _issue(
                        "mixed_run_pf_verification_result",
                        "signed.verification_result.status must be ProofChecked",
                    ),
                )
            embedded_refs = _vr_certificate_refs(embedded_vr)
            if embedded_refs:
                cert_ids["signed.verification_result"] = embedded_refs[0]

    unique_cert_ids = {cid for cid in cert_ids.values() if isinstance(cid, str)}
    if len(unique_cert_ids) > 1:
        details = ", ".join(f"{label}={cid}" for label, cid in cert_ids.items() if cid)
        issues.append(
            _issue(
                "mixed_run_certificate_id",
                f"certificate_id mismatch across release chain artifacts ({details})",
            ),
        )

    if certified and signed:
        scb = signed.get("science_claim_bundle")
        if not isinstance(scb, dict):
            issues.append(
                _issue(
                    "mixed_run_certificate_id",
                    "signed_science_claim_bundle missing science_claim_bundle object",
                ),
            )
        elif not _json_equal(certified, scb):
            issues.append(
                _issue(
                    "mixed_run_certificate_id",
                    "signed.science_claim_bundle does not match science_claim_bundle.certified.json "
                    "(excluding signature_or_digest fields)",
                ),
            )

    if verification and signed:
        embedded_vr = signed.get("verification_result")
        if not isinstance(embedded_vr, dict):
            issues.append(
                _issue(
                    "mixed_run_pf_verification_result",
                    "signed_science_claim_bundle missing verification_result object",
                ),
            )
        elif not _json_equal(verification, embedded_vr):
            issues.append(
                _issue(
                    "mixed_run_pf_verification_result",
                    "signed.verification_result does not match verification_result.json "
                    "(excluding signature_or_digest fields)",
                ),
            )

    if sm_report and sm_report.get("verification_status") != "passed":
        issues.append(
            _issue(
                "invalid_artifact",
                "scientific_memory_import_report.verification_status must be passed",
            ),
        )

    return issues


def validate_release_chain_messages(directory: Path) -> list[str]:
    return [issue.format() for issue in validate_release_chain(directory)]
