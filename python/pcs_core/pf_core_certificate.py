"""PF-Core certificate construction helpers."""

from __future__ import annotations

from typing import Any, Mapping

from pcs_core.hash import canonical_hash
from pcs_core.lean_check import PF_CORE_ASSUMPTION_REFS
from pcs_core.pf_core_runtime import GENESIS_HASH

CERTIFICATE_CHECK_DISCLAIMER = (
    "CertificateChecked attests that an external checker (e.g. CertifyEdge) evaluated "
    "the trace against a declared property. This claim class does not imply "
    "LeanKernelChecked or ReplayValidated assurance."
)


def attach_external_certificate_check(
    trace: Mapping[str, Any],
    *,
    checker: str,
    checker_version: str,
    external_status: str = "CertificateChecked",
    attestation_ref: str | None = None,
    assumption_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Wrap an external checker attestation into PFCoreCertificate.v0."""
    events = trace.get("events")
    event_count = len(events) if isinstance(events, list) else 0
    refs = list(assumption_refs or PF_CORE_ASSUMPTION_REFS)
    if attestation_ref:
        refs.append(attestation_ref)

    cert: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": f"pfcore-ext-{trace.get('trace_id', 'unknown')}",
        "trace_hash": str(trace.get("trace_hash") or GENESIS_HASH),
        "contract_hash": str(trace.get("contract_hash") or GENESIS_HASH),
        "policy_hash": str(trace.get("policy_hash") or GENESIS_HASH),
        "claim_class": "CertificateChecked",
        "checker": checker,
        "checker_version": checker_version,
        "assumption_refs": refs,
        "obligations": [
            {
                "kind": "ExternalCheckerAttestation",
                "theorem": "external_checker_attestation",
                "passed": external_status == "CertificateChecked",
                "proof_ref": attestation_ref,
            }
        ],
        "disclaimer": CERTIFICATE_CHECK_DISCLAIMER,
        "event_count": event_count,
        "source_repo": str(trace.get("source_repo") or "https://github.com/example/pcs-core"),
        "source_commit": str(trace.get("source_commit") or "0000000"),
        "signature_or_digest": GENESIS_HASH,
    }
    cert["signature_or_digest"] = canonical_hash(cert)
    return cert
