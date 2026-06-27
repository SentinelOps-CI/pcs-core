"""Generate deferred PF-Core invalid fixtures and shared hash vectors."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pcs_core.hash import canonical_hash, canonicalize_for_hash
from pcs_core.pf_core_contract import default_trace_safe_contract
from pcs_core.pf_core_runtime import (
    GENESIS_HASH,
    compute_event_hash,
    compute_trace_hash,
)

ROOT = Path(__file__).resolve().parents[2]
INVALID = ROOT / "examples" / "pf-core-invalid"
VALID = ROOT / "examples" / "pf-core-valid"
HASH_ROOT = ROOT / "python" / "tests" / "hash_vectors" / "pf_core"


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_manifest(case_dir: Path, *, expected_error: str, must_fail_at: str, **extra: object) -> None:
    payload = {"expected_error": expected_error, "must_fail_at": must_fail_at, **extra}
    write_json(case_dir / "manifest.json", payload)


def base_event(*, decision: str = "allow", contract_refs: list[str] | None = None) -> dict:
    return {
        "schema_version": "v0",
        "artifact_type": "PFCoreEvent.v0",
        "event_id": "ev-file-read-1",
        "trace_id": "trace-file-read-1",
        "sequence": 0,
        "timestamp": "2026-06-18T00:00:00Z",
        "principal": {
            "principal_id": "agent-1",
            "principal_kind": "agent",
            "tenant": "tenant-a",
            "roles": ["agent"],
            "capabilities": [
                "cap:file-read",
                "cap:email-send",
                "cap:handoff",
                "cap:mcp-invoke",
            ],
        },
        "action": {
            "action_id": "act-1",
            "tool_name": "filesystem.read",
            "capability": {
                "capability_id": "cap:file-read",
                "effect_kind": "file.read",
                "resource_pattern": "/data/*",
            },
            "effects": [{"effect_kind": "file.read"}],
            "reads": [
                {
                    "resource_id": "res-1",
                    "uri": "/data/report.txt",
                    "tenant": "tenant-a",
                }
            ],
            "writes": [],
            "input_hash": "sha256:" + "a" * 64,
            "output_hash": "sha256:" + "b" * 64,
        },
        "decision": decision,
        "decision_reason": "authorized" if decision == "allow" else "denied",
        "contract_refs": list(contract_refs or []),
        "evidence_refs": [],
        "previous_event_hash": GENESIS_HASH,
        "event_hash": GENESIS_HASH,
        "source_repo": "https://github.com/example/agent-runtime",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": GENESIS_HASH,
    }


def finalize_trace(trace: dict) -> dict:
    events = trace["events"]
    previous = GENESIS_HASH
    for event in events:
        event["previous_event_hash"] = previous
        event_hash = compute_event_hash(event)
        event["event_hash"] = event_hash
        event["signature_or_digest"] = event_hash
        previous = event_hash
    trace["trace_hash"] = compute_trace_hash(trace)
    trace["signature_or_digest"] = trace["trace_hash"]
    return trace


def base_trace(**kwargs: object) -> dict:
    trace = {
        "schema_version": "v0",
        "artifact_type": "PFCoreTrace.v0",
        "trace_id": "trace-file-read-1",
        "workflow_id": "agent_tool_use.safety_v0",
        "events": [base_event()],
        "trace_hash": GENESIS_HASH,
        "policy_hash": GENESIS_HASH,
        "contract_hash": GENESIS_HASH,
        "claim_class": "RuntimeChecked",
        "source_repo": "https://github.com/example/agent-runtime",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": GENESIS_HASH,
    }
    trace.update(kwargs)
    return finalize_trace(trace)


def strict_contract(**overrides: object) -> dict:
    contract = {
        "schema_version": "v0",
        "artifact_type": "PFCoreContract.v0",
        "contract_id": "contract-file-read-v0",
        "name": "Strict file read contract",
        "pre": {
            "require_capability": "cap:file-read",
            "require_effect": "file.read",
            "require_tenant_match": True,
            "require_policy_ref": "policy/default.v0",
            "require_evidence_ref": "evidence/run-1",
        },
        "post": {
            "require_decision": "allow",
            "require_event_safe": True,
        },
        "invariant": {"require_trace_safe": True},
        "signature_or_digest": GENESIS_HASH,
    }
    contract.update(overrides)
    contract["signature_or_digest"] = canonical_hash(
        {k: v for k, v in contract.items() if k != "signature_or_digest"}
    )
    return contract


def observation(*, decision: str, event_id: str, sequence: int) -> dict:
    return {
        "schema_version": "v0",
        "artifact_type": "PFCoreRuntimeObservation.v0",
        "observation_id": f"obs-{event_id}",
        "trace_id": "trace-obs-batch-1",
        "event_id": event_id,
        "sequence": sequence,
        "observed_at": "2026-06-18T00:00:00Z",
        "principal": {
            "principal_id": "agent-1",
            "principal_kind": "agent",
            "tenant": "tenant-a",
            "roles": ["agent"],
            "capabilities": ["cap:file-read"],
        },
        "action": {
            "action_id": "act-1",
            "tool_name": "filesystem.read",
            "capability": {
                "capability_id": "cap:file-read",
                "effect_kind": "file.read",
                "resource_pattern": "/data/*",
            },
            "effects": [{"effect_kind": "file.read"}],
            "reads": [
                {
                    "resource_id": "res-1",
                    "uri": "/data/report.txt",
                    "tenant": "tenant-a",
                }
            ],
            "writes": [],
            "input_hash": "sha256:" + "a" * 64,
            "output_hash": "sha256:" + "b" * 64,
        },
        "decision": decision,
        "decision_reason": decision,
        "policy_ref": "policy/default.v0",
        "evidence_refs": [],
        "runtime_ref": "agent-runtime",
        "previous_event_hash": GENESIS_HASH,
        "payload_hash": "sha256:" + "c" * 64,
        "claim_class": "RuntimeChecked",
        "source_repo": "https://github.com/example/agent-runtime",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": "sha256:" + "d" * 64,
    }


def generate_invalid_fixtures() -> None:
    case = INVALID / "previous_event_hash_mismatch"
    trace = base_trace()
    trace = finalize_trace(trace)
    trace["events"][0]["previous_event_hash"] = "sha256:" + "f" * 64
    write_json(case / "trace.json", trace)
    write_manifest(case, expected_error="EventHashMismatch", must_fail_at="validate_pfcore_trace_hash_chain")

    case = INVALID / "lean_kernel_checked_without_proof_ref"
    trace = base_trace(claim_class="LeanKernelChecked")
    trace["events"][0]["contract_refs"] = ["contract-file-read-v0"]
    trace = finalize_trace(trace)
    write_json(case / "trace.json", trace)
    write_manifest(
        case,
        expected_error="ClaimClassOverclaim",
        must_fail_at="validate_semantics",
        artifact_file="trace.json",
        artifact_type="PFCoreTrace.v0",
    )

    case = INVALID / "lean_kernel_checked_without_contract"
    trace = base_trace(claim_class="LeanKernelChecked")
    write_json(case / "trace.json", trace)
    write_manifest(
        case,
        expected_error="ContractBindingMissing",
        must_fail_at="validate_semantics",
        artifact_file="trace.json",
        artifact_type="PFCoreTrace.v0",
    )

    case = INVALID / "lean_kernel_checked_without_proof_term_ref"
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-missing-proof-term",
        "trace_hash": GENESIS_HASH,
        "contract_hash": GENESIS_HASH,
        "policy_hash": GENESIS_HASH,
        "claim_class": "LeanKernelChecked",
        "checker": "pcs-core",
        "checker_version": "0.1.0",
        "assumption_refs": ["docs/pf-core/assumptions.md"],
        "theorems_checked": ["traceSafeD"],
        "obligations": [],
        "lean_build_status": {"ok": True, "target": "PFCore", "detail": "ok"},
        "lean_proof_checked": True,
        "lean_environment_hash": "sha256:" + "e" * 64,
        "proof_ref": "lean/PFCore/Generated/example.lean",
        "disclaimer": "test fixture",
        "event_count": 1,
        "contract_semantics_checked": {"lean": ["trace-safe.invariant.require_trace_safe"], "runtime": []},
        "default_contract_ref": "trace-safe",
        "source_repo": "https://github.com/example/pcs-core",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": GENESIS_HASH,
    }
    cert["signature_or_digest"] = canonical_hash(cert)
    write_json(case / "certificate.json", cert)
    write_manifest(
        case,
        expected_error="proof_term_ref",
        must_fail_at="validate_semantics",
        artifact_file="certificate.json",
        artifact_type="PFCoreCertificate.v0",
    )

    case = INVALID / "lean_kernel_checked_with_skipped_build"
    cert = dict(cert)
    cert["certificate_id"] = "pfcore-cert-skipped-build"
    cert["proof_term_ref"] = cert["proof_ref"]
    cert["lean_build_status"] = {"ok": False, "target": "PFCore", "detail": "skipped"}
    cert["signature_or_digest"] = canonical_hash({k: v for k, v in cert.items() if k != "signature_or_digest"})
    write_json(case / "certificate.json", cert)
    write_manifest(
        case,
        expected_error="lean_build_status.ok=true",
        must_fail_at="validate_semantics",
        artifact_file="certificate.json",
        artifact_type="PFCoreCertificate.v0",
    )

    case = INVALID / "cross_tenant_allowed_event"
    if not case.is_dir():
        shutil.copytree(INVALID / "cross_tenant_leak", case)
        write_manifest(case, expected_error="TenantIsolation", must_fail_at="validate_tenant_isolation")

    case = INVALID / "contract_ref_missing"
    trace = base_trace()
    trace["events"][0]["contract_refs"] = ["contract-missing-v0"]
    trace = finalize_trace(trace)
    write_json(case / "trace.json", trace)
    write_manifest(case, expected_error="ContractRefMissing", must_fail_at="validate_trace_contracts")

    def contract_case(
        name: str,
        expected_error: str,
        mutate_event,
        *,
        contract: dict[str, object] | None = None,
    ) -> None:
        case_dir = INVALID / name
        contract_obj = dict(contract or strict_contract())
        event = base_event(contract_refs=[str(contract_obj["contract_id"])])
        mutate_event(event)
        trace = base_trace(events=[event])
        write_json(case_dir / "trace.json", trace)
        write_json(case_dir / "contracts" / "contract.json", contract_obj)
        write_manifest(case_dir, expected_error=expected_error, must_fail_at="validate_trace_contracts")

    contract_case(
        "contract_capability_missing",
        "ContractCapabilityRequired",
        lambda event: (
            event["principal"].update(
                {
                    "roles": ["email_user"],
                    "capabilities": ["cap:email-send"],
                }
            )
        ),
        contract={
            **strict_contract(),
            "pre": {"require_capability": "cap:file-read"},
            "post": {},
            "invariant": {},
        },
    )
    contract_case(
        "contract_effect_missing",
        "ContractEffectRequired",
        lambda event: event["action"].update(
            {
                "effects": [{"effect_kind": "file.write"}],
                "capability": {
                    "capability_id": "cap:file-write",
                    "effect_kind": "file.write",
                    "resource_pattern": "/data/*",
                },
            }
        ),
        contract={
            **strict_contract(),
            "pre": {"require_effect": "file.read"},
            "post": {},
            "invariant": {},
        },
    )
    contract_case(
        "contract_policy_ref_missing",
        "ContractPolicyRefRequired",
        lambda event: event.update({"contract_refs": ["contract-file-read-v0"]}),
        contract={
            **strict_contract(),
            "pre": {"require_policy_ref": "policy/default.v0"},
            "post": {},
            "invariant": {},
        },
    )
    contract_case(
        "contract_evidence_ref_missing",
        "ContractEvidenceRefRequired",
        lambda event: event.update({"evidence_refs": []}),
        contract={
            **strict_contract(),
            "pre": {"require_evidence_ref": "evidence/run-1"},
            "post": {},
            "invariant": {},
        },
    )

    case = INVALID / "dropped_denied_observation"
    write_json(case / "observation_0.json", observation(decision="allow", event_id="ev-allow", sequence=0))
    write_json(
        case / "observation_1.json",
        observation(decision="deny", event_id="ev-deny", sequence=1),
    )
    pfcore = base_trace(
        trace_id="trace-obs-batch-1",
        events=[
            finalize_trace(base_trace())["events"][0],
        ],
    )
    pfcore["events"][0]["event_id"] = "ev-allow"
    pfcore["events"][0]["decision"] = "allow"
    pfcore = finalize_trace(pfcore)
    write_json(case / "pfcore_trace.json", pfcore)
    write_manifest(
        case,
        expected_error="DroppedDeniedEvent",
        must_fail_at="validate_denied_observations_preserved",
    )


def write_hash_vector(name: str, payload: dict, *, digest: str, canonical: str) -> None:
    target = HASH_ROOT / name
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "input.json", payload)
    (target / "canonical.txt").write_text(canonical + "\n", encoding="utf-8")
    (target / "digest.txt").write_text(digest + "\n", encoding="utf-8")


def generate_hash_vectors() -> None:
    from pcs_core.hash import canonicalize_for_hash

    event_path = VALID / "file_read_allowed" / "event.json"
    trace_path = VALID / "file_read_allowed" / "trace.json"
    event = json.loads(event_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    event_canonical = json.dumps(
        canonicalize_for_hash({k: v for k, v in event.items() if k not in ("event_hash", "signature_or_digest")}),
        separators=(",", ":"),
        ensure_ascii=False,
    )
    trace_canonical = json.dumps(
        canonicalize_for_hash({k: v for k, v in trace.items() if k not in ("trace_hash", "signature_or_digest")}),
        separators=(",", ":"),
        ensure_ascii=False,
    )
    write_hash_vector(
        "PFCoreEvent.v0",
        event,
        digest=compute_event_hash(event),
        canonical=event_canonical,
    )
    write_hash_vector(
        "PFCoreTrace.v0",
        trace,
        digest=compute_trace_hash(trace),
        canonical=trace_canonical,
    )
    contract = default_trace_safe_contract()
    contract_canonical = json.dumps(
        canonicalize_for_hash({k: v for k, v in contract.items() if k != "signature_or_digest"}),
        separators=(",", ":"),
        ensure_ascii=False,
    )
    write_hash_vector(
        "PFCoreContract.v0",
        contract,
        digest=canonical_hash(contract),
        canonical=contract_canonical,
    )


def main() -> None:
    generate_invalid_fixtures()
    generate_hash_vectors()
    print("generated deferred PF-Core fixtures and hash vectors")


if __name__ == "__main__":
    main()
