"""Atomic PCS v0.1 LabTrust release-chain validation."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pcs_core.bundle_identity import resolve_certified_bundle_identity_hash
from pcs_core.release_fixtures import (
    CERTIFYEDGE_SOURCE_REPO,
    COMMIT_KEYS,
    LABTRUST_SOURCE_REPO,
    MANIFEST_ARTIFACTS,
    MANIFEST_NAME,
    PF_SOURCE_REPO,
    RELEASE_PCS_ARTIFACTS,
    _load_json,
    _scan_forbidden_values,
    _validate_trace_hash_alignment,
    file_digest,
    is_release_pattern_placeholder,
    is_zero_commit,
)
from pcs_core.validate import ValidationError, validate_file

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReleaseChainIssue:
    code: str
    message: str
    artifact: str | None = None
    expected: Any = None
    actual: Any = None

    def format(self) -> str:
        return f"{self.code}: {self.message}"


def _issue(
    code: str,
    message: str,
    *,
    artifact: str | None = None,
    expected: Any = None,
    actual: Any = None,
) -> ReleaseChainIssue:
    return ReleaseChainIssue(
        code=code,
        message=message,
        artifact=artifact,
        expected=expected,
        actual=actual,
    )


def _validate_trace_json(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    trace_hash = doc.get("trace_hash")
    if not isinstance(trace_hash, str) or not _DIGEST_RE.fullmatch(trace_hash):
        errors.append("trace.json: trace_hash must be a sha256 digest")
    if not doc.get("events"):
        errors.append("trace.json: events are required")
    return errors


def _validate_scientific_memory_report_json(doc: dict[str, Any]) -> list[str]:
    required = (
        "verification_status",
        "strict",
        "allow_legacy",
        "bundle_shape",
        "source_commit",
        "scientific_memory_commit",
    )
    return [
        f"scientific_memory_import_report.json: missing required field {key}"
        for key in required
        if key not in doc
    ]


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


def _certificate_ref_contains(bundle: dict[str, Any], part_key: str, certificate_id: str) -> bool:
    part = bundle.get(part_key)
    if not isinstance(part, dict):
        return False
    certificate_refs = part.get("certificate_refs")
    if not isinstance(certificate_refs, list):
        return False
    return certificate_id in certificate_refs


def _expect_certificate_id(
    issues: list[ReleaseChainIssue],
    *,
    expected: str,
    actual: str | None,
    label: str,
    artifact: str,
) -> None:
    if actual is None:
        issues.append(
            _issue(
                "certificate_id_mismatch",
                f"{label}: certificate ID is required",
                artifact=artifact,
                expected=expected,
            ),
        )
    elif actual != expected:
        issues.append(
            _issue(
                "certificate_id_mismatch",
                f"{label}: expected {expected!r}, got {actual!r}",
                artifact=artifact,
                expected=expected,
                actual=actual,
            ),
        )


def _expect_certificate_ref_contains(
    issues: list[ReleaseChainIssue],
    *,
    bundle: dict[str, Any],
    part_key: str,
    certificate_id: str,
    artifact: str,
) -> None:
    label = f"science_claim_bundle.certified.{part_key}.certificate_refs"
    if not _certificate_ref_contains(bundle, part_key, certificate_id):
        issues.append(
            _issue(
                "certificate_id_mismatch",
                f"{label} must contain {certificate_id!r}",
                artifact=artifact,
                expected=certificate_id,
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
    """Validate a complete release directory for single-run atomic consistency.

    Compatibility entry point: delegates to the declarative release-profile engine.
    """
    from pcs_core.release_profile_engine import validate_release_directory

    return validate_release_directory(directory)


def _validate_labtrust_release_chain_impl(directory: Path) -> list[ReleaseChainIssue]:
    """LabTrust domain validator body (legacy; invoked via ReleaseProfileSpec)."""
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
        elif is_zero_commit(commit):
            issues.append(
                _issue(
                    "placeholder_commit_detected",
                    f"manifest {key} uses zero provenance: {commit}",
                    artifact=MANIFEST_NAME,
                ),
            )
        elif is_release_pattern_placeholder(commit):
            issues.append(
                _issue(
                    "placeholder_commit_detected",
                    f"manifest {key} uses pattern placeholder provenance: {commit}",
                    artifact=MANIFEST_NAME,
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
            issues.append(
                _issue("schema_validation_failed", f"manifest artifacts missing keys: {missing}")
            )
        if extra:
            issues.append(
                _issue("schema_validation_failed", f"manifest artifacts unexpected keys: {extra}")
            )

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
                    artifact=name,
                    expected=expected,
                    actual=actual,
                ),
            )

    scan_errors: list[str] = []
    for name in MANIFEST_ARTIFACTS:
        path = base / name
        if not path.is_file():
            continue
        doc = _load_json(path)
        if doc is None:
            issues.append(
                _issue("schema_validation_failed", f"{name}: invalid JSON", artifact=name),
            )
            continue
        if name == "trace.json":
            for msg in _validate_trace_json(doc):
                issues.append(_issue("schema_validation_failed", msg, artifact=name))
        elif name == "scientific_memory_import_report.json":
            for msg in _validate_scientific_memory_report_json(doc):
                issues.append(_issue("schema_validation_failed", msg, artifact=name))
        _scan_forbidden_values(doc, label=name, errors=scan_errors)
    for msg in scan_errors:
        artifact = msg.split(":", 1)[0] if ":" in msg else None
        if "local_dev" in msg:
            issues.append(_issue("local_dev_detected", msg, artifact=artifact))
        elif "zero" in msg:
            issues.append(_issue("placeholder_commit_detected", msg, artifact=artifact))
        elif "placeholder" in msg:
            issues.append(_issue("placeholder_commit_detected", msg, artifact=artifact))
        else:
            issues.append(_issue("schema_validation_failed", msg, artifact=artifact))

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
            issues.append(
                _issue(
                    "schema_validation_failed",
                    f"{name}: pcs validate failed: {exc}",
                    artifact=name,
                ),
            )

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

    trace_cert_id = trace_cert.get("certificate_id") if trace_cert else None
    certified_cert_id = _first_certificate_id(certified) if certified else None
    signed_scb = signed.get("science_claim_bundle") if signed else None

    if trace_cert_id and certified and isinstance(certified, dict):
        _expect_certificate_id(
            issues,
            expected=trace_cert_id,
            actual=certified_cert_id,
            label="science_claim_bundle.certified.certificates[0].certificate_id",
            artifact="science_claim_bundle.certified.json",
        )
        _expect_certificate_ref_contains(
            issues,
            bundle=certified,
            part_key="claim_artifact",
            certificate_id=trace_cert_id,
            artifact="science_claim_bundle.certified.json",
        )
        _expect_certificate_ref_contains(
            issues,
            bundle=certified,
            part_key="evidence_bundle",
            certificate_id=trace_cert_id,
            artifact="science_claim_bundle.certified.json",
        )
        _expect_certificate_id(
            issues,
            expected=trace_cert_id,
            actual=_verified_input_certificate_id(verification) if verification else None,
            label="verification_result.verified_input.certificate_id",
            artifact="verification_result.json",
        )
        if isinstance(signed_scb, dict):
            _expect_certificate_id(
                issues,
                expected=trace_cert_id,
                actual=_first_certificate_id(signed_scb),
                label="signed_science_claim_bundle.science_claim_bundle.certificates[0].certificate_id",
                artifact="signed_science_claim_bundle.json",
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

    bundle_identity = resolve_certified_bundle_identity_hash(
        base,
        manifest_artifacts=artifacts if isinstance(artifacts, dict) else None,
    )
    if bundle_identity and verification:
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
            elif bundle_hash != bundle_identity:
                issues.append(
                    _issue(
                        "verified_input_hash_mismatch",
                        f"verified_input.bundle_hash {bundle_hash} "
                        f"!= certified bundle identity hash {bundle_identity}",
                    ),
                )
    if signed and bundle_identity:
        signed_hash = signed.get("signed_input_bundle_hash")
        if not signed_hash:
            issues.append(
                _issue(
                    "signed_input_hash_mismatch",
                    "signed_science_claim_bundle.signed_input_bundle_hash is required",
                ),
            )
        elif signed_hash != bundle_identity:
            issues.append(
                _issue(
                    "signed_input_hash_mismatch",
                    f"signed_input_bundle_hash {signed_hash} != certified bundle identity hash "
                    f"{bundle_identity}",
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


def validate_release_chain_report(directory: Path) -> dict[str, Any]:
    from pcs_core.release_chain_report import build_release_chain_report

    return build_release_chain_report(directory)
