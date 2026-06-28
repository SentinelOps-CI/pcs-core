"""Minimal LabTrust release → PFCoreTrace adapter (untrusted, schema-validated)."""

from __future__ import annotations

from typing import Any, Mapping

from pcs_core.pf_core_runtime import (
    GENESIS_HASH,
    _finalize_event,
    _validate_action,
    _validate_principal,
    compute_trace_hash,
    expand_principal_capabilities,
)

LABTRUST_PRINCIPAL = {
    "principal_id": "lab-operator-1",
    "principal_kind": "human",
    "tenant": "labtrust-qc",
    "roles": ["lab_operator"],
    "capabilities": [],
}


def normalize_labtrust_release(
    trace_certificate: Mapping[str, Any],
    runtime_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a single-event PFCoreTrace.v0 from LabTrust PCS release artifacts.

    Maps PCS trace_certificate trace_hash/spec_hash to PF-Core trace/certificate
    binding fields per docs/pf-core-trace-mapping.md.
    """
    receipt = runtime_receipt or {}
    trace_id = str(receipt.get("run_id") or "labtrust-qc-release-v0.1").replace("/", "-")
    timestamp = str(
        receipt.get("started_at") or trace_certificate.get("created_at") or "2026-05-16T11:58:00Z"
    )
    source_repo = str(trace_certificate.get("source_repo") or receipt.get("source_repo") or "")
    source_commit = str(
        trace_certificate.get("source_commit") or receipt.get("source_commit") or ""
    )

    principal = _validate_principal(dict(LABTRUST_PRINCIPAL))
    principal["capabilities"] = expand_principal_capabilities(principal)

    action = _validate_action(
        {
            "action_id": "act-lab-release-001",
            "tool_name": "lab.release",
            "capability": {
                "capability_id": "cap:lab-release",
                "effect_kind": "lab.release",
                "resource_pattern": "lab:*",
            },
            "effects": [{"effect_kind": "lab.release"}],
            "reads": [
                {
                    "resource_id": "res-lab-release-001",
                    "uri": "lab:qc-release/run-001",
                    "tenant": principal["tenant"],
                }
            ],
            "writes": [],
            "input_hash": str(
                receipt.get("events_hash") or trace_certificate.get("trace_hash") or GENESIS_HASH
            ),
            "output_hash": str(
                receipt.get("output_hashes", {}).get("trace.json")
                if isinstance(receipt.get("output_hashes"), dict)
                else trace_certificate.get("trace_hash") or GENESIS_HASH
            ),
        }
    )

    event = _finalize_event(
        trace_id=trace_id,
        event_id="evt-lab-release-001",
        sequence=0,
        timestamp=timestamp,
        principal=principal,
        action=action,
        decision="allow",
        decision_reason="CertificateChecked",
        contract_refs=[str(trace_certificate.get("property_id") or "qc_release.temporal.safety")],
        evidence_refs=[str(trace_certificate.get("certificate_id") or "")],
        previous_event_hash=GENESIS_HASH,
        source_repo=source_repo,
        source_commit=source_commit,
    )

    policy_hash = str(receipt.get("policy_hash") or GENESIS_HASH)
    contract_hash = str(trace_certificate.get("spec_hash") or GENESIS_HASH)

    trace: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreTrace.v0",
        "trace_id": trace_id,
        "workflow_id": "labtrust.qc_release.v0",
        "events": [event],
        "trace_hash": GENESIS_HASH,
        "policy_hash": policy_hash,
        "contract_hash": contract_hash,
        "claim_class": "RuntimeChecked",
        "source_repo": source_repo,
        "source_commit": source_commit,
        "signature_or_digest": GENESIS_HASH,
    }
    trace["trace_hash"] = compute_trace_hash(trace)
    trace["signature_or_digest"] = trace["trace_hash"]
    return trace
