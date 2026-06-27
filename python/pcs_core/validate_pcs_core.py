"""PCS core semantic validation helpers."""

import re
from typing import Any

from pcs_core.status import ARTIFACT_STATUSES, TRACE_CERTIFICATE_STATUSES

_ZERO_COMMIT_RE = re.compile(r"^0+$")

CERTIFIED_CLAIM_STATUSES = frozenset(
    {
        "CertificateChecked",
        "ProofChecked",
        "RuntimeChecked",
    }
)

IMPORT_READY_VERIFICATION_STATUSES = frozenset(
    {
        "ProofChecked",
        "CertificateChecked",
        "RuntimeChecked",
    }
)
def _is_zero_source_commit(value: str) -> bool:
    return bool(_ZERO_COMMIT_RE.match(value.strip()))


def _local_dev_enabled(obj: dict[str, Any], inherited: bool) -> bool:
    if inherited:
        return True
    if obj.get("local_dev") is True:
        return True
    return False


def _check_source_commits(
    obj: Any,
    path: str,
    errors: list[str],
    *,
    inherited_local_dev: bool = False,
) -> None:
    if isinstance(obj, dict):
        local_dev = _local_dev_enabled(obj, inherited_local_dev)
        commit = obj.get("source_commit")
        if isinstance(commit, str) and _is_zero_source_commit(commit) and not local_dev:
            errors.append(
                f"{path or 'root'}: zero source_commit not allowed without local_dev=true"
            )
        for key, value in obj.items():
            child = f"{path}.{key}" if path else key
            _check_source_commits(value, child, errors, inherited_local_dev=local_dev)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _check_source_commits(
                item,
                f"{path}[{index}]",
                errors,
                inherited_local_dev=inherited_local_dev,
            )


def _validate_status_fields(obj: Any, path: str, errors: list[str]) -> None:
    if isinstance(obj, dict):
        if "check_id" not in obj:
            status = obj.get("status")
            if isinstance(status, str):
                if "certificate_id" in obj:
                    if status not in TRACE_CERTIFICATE_STATUSES:
                        errors.append(f"{path}: invalid TraceCertificate status {status!r}")
                elif status not in ARTIFACT_STATUSES:
                    errors.append(f"{path}: unknown status {status!r}")
        for key, value in obj.items():
            child = f"{path}.{key}" if path else key
            _validate_status_fields(value, child, errors)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _validate_status_fields(item, f"{path}[{index}]", errors)


def _validate_science_claim_bundle(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    assumption_set = data.get("assumption_set")
    if not isinstance(assumption_set, dict):
        errors.append("ScienceClaimBundle.v0 requires assumption_set")
    else:
        assumptions = assumption_set.get("assumptions")
        if not assumptions:
            errors.append("ScienceClaimBundle.v0 requires non-empty assumption_set.assumptions")

    receipts = data.get("runtime_receipts")
    if not isinstance(receipts, list) or len(receipts) == 0:
        errors.append("ScienceClaimBundle.v0 requires non-empty runtime_receipts")

    claim = data.get("claim_artifact")
    if isinstance(claim, dict):
        ref = claim.get("assumption_set_ref")
        if not ref or not str(ref).strip():
            errors.append("claim_artifact requires non-empty assumption_set_ref")
        elif isinstance(assumption_set, dict):
            if ref != assumption_set.get("assumption_set_id"):
                errors.append(
                    "claim_artifact.assumption_set_ref must match assumption_set.assumption_set_id"
                )

    certificates = data.get("certificates")
    if not isinstance(certificates, list):
        certificates = []

    claim_status = str(claim.get("status") or "") if isinstance(claim, dict) else ""
    if claim_status in CERTIFIED_CLAIM_STATUSES and len(certificates) == 0:
        errors.append("certified ScienceClaimBundle requires at least one TraceCertificate")

    if isinstance(receipts, list):
        for receipt in receipts:
            if not isinstance(receipt, dict):
                continue
            r_hash = receipt.get("trace_hash")
            for cert in certificates:
                if not isinstance(cert, dict):
                    continue
                c_status = str(cert.get("status") or "")
                if c_status and c_status not in TRACE_CERTIFICATE_STATUSES:
                    errors.append(
                        f"TraceCertificate {cert.get('certificate_id')}: "
                        f"invalid status {c_status!r}"
                    )
                c_hash = cert.get("trace_hash")
                if r_hash and c_hash and r_hash != c_hash:
                    errors.append(
                        f"trace_hash mismatch: receipt {receipt.get('receipt_id')} "
                        f"({r_hash}) vs certificate {cert.get('certificate_id')} ({c_hash})"
                    )

    return errors


def _validate_verification_result(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    checks = data.get("checks")
    if not isinstance(checks, list):
        return errors
    has_failed = any(
        isinstance(check, dict) and check.get("status") == "failed" for check in checks
    )
    top_status = str(data.get("status") or "")
    if has_failed and top_status in IMPORT_READY_VERIFICATION_STATUSES:
        errors.append(
            "VerificationResult.v0 with failed checks cannot use import-ready status "
            f"{top_status!r} (Scientific Memory import contract)"
        )
    return errors


def _validate_signed_bundle(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scb = data.get("science_claim_bundle")
    if isinstance(scb, dict):
        errors.extend(_validate_science_claim_bundle(scb))
    vr = data.get("verification_result")
    if isinstance(vr, dict):
        _validate_status_fields(vr, "verification_result", errors)
        errors.extend(_validate_verification_result(vr))
    return errors

