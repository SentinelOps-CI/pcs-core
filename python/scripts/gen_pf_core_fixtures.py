"""Generate PF-Core Stage 2 example fixtures (dev utility)."""

from __future__ import annotations

import json
from pathlib import Path

from pcs_core.hash import canonical_hash
from pcs_core.pf_core_runtime import (
    GENESIS_HASH,
    compile_runtime_observation_to_event,
    compile_tool_use_trace_to_pfcore_trace,
    compute_trace_hash,
)
from pcs_core.paths import repo_root

ROOT = repo_root() / "examples"
VALID = ROOT / "pf-core-valid"
INVALID = ROOT / "pf-core-invalid"


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _finalize_obs(base: dict) -> dict:
    payload = {key: value for key, value in base.items() if key != "signature_or_digest"}
    base["payload_hash"] = canonical_hash(payload)
    base["signature_or_digest"] = base["payload_hash"]
    return base


def _base_obs(**overrides: object) -> dict:
    obs = _finalize_obs(
        {
            "schema_version": "v0",
            "artifact_type": "PFCoreRuntimeObservation.v0",
            "observation_id": "obs-1",
            "trace_id": "trace-1",
            "event_id": "ev-1",
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
            "decision": "allow",
            "decision_reason": "authorized",
            "policy_ref": "policy/default.v0",
            "evidence_refs": [],
            "runtime_ref": "agent-runtime",
            "previous_event_hash": GENESIS_HASH,
            "payload_hash": GENESIS_HASH,
            "claim_class": "RuntimeChecked",
            "source_repo": "https://github.com/example/agent-runtime",
            "source_commit": "abc1234567890abc1234567890abc1234567890",
            "signature_or_digest": GENESIS_HASH,
        }
    )
    obs.update(overrides)
    return _finalize_obs(obs)


def _trace_from_event(event: dict, *, trace_id: str, workflow_id: str) -> dict:
    trace = {
        "schema_version": "v0",
        "artifact_type": "PFCoreTrace.v0",
        "trace_id": trace_id,
        "workflow_id": workflow_id,
        "events": [event],
        "trace_hash": GENESIS_HASH,
        "policy_hash": GENESIS_HASH,
        "contract_hash": GENESIS_HASH,
        "claim_class": "RuntimeChecked",
        "source_repo": event["source_repo"],
        "source_commit": event["source_commit"],
        "signature_or_digest": GENESIS_HASH,
    }
    trace["trace_hash"] = compute_trace_hash(trace)
    trace["signature_or_digest"] = trace["trace_hash"]
    return trace


def main() -> None:
    file_read = _base_obs(
        observation_id="obs-file-read-1",
        trace_id="trace-file-read-1",
        event_id="ev-file-read-1",
    )
    file_read_event = compile_runtime_observation_to_event(file_read)
    file_read_trace = _trace_from_event(
        file_read_event,
        trace_id="trace-file-read-1",
        workflow_id="agent_tool_use.safety_v0",
    )
    _write(VALID / "file_read_allowed" / "observation.json", file_read)
    _write(VALID / "file_read_allowed" / "event.json", file_read_event)
    _write(VALID / "file_read_allowed" / "trace.json", file_read_trace)
    _write(
        VALID / "file_read_allowed" / "manifest.json",
        {"description": "Allowed file read within tenant"},
    )

    denied_cross = _base_obs(
        observation_id="obs-denied-tenant-1",
        trace_id="trace-denied-tenant-1",
        event_id="ev-denied-tenant-1",
        decision="allow",
        action={
            "action_id": "act-denied-1",
            "tool_name": "filesystem.read",
            "capability": {
                "capability_id": "cap:file-read",
                "effect_kind": "file.read",
                "resource_pattern": "/data/*",
            },
            "effects": [{"effect_kind": "file.read"}],
            "reads": [
                {
                    "resource_id": "res-x",
                    "uri": "/data/secret.txt",
                    "tenant": "tenant-b",
                }
            ],
            "writes": [],
            "input_hash": "sha256:" + "c" * 64,
            "output_hash": "sha256:" + "d" * 64,
        },
    )
    denied_event = compile_runtime_observation_to_event(denied_cross)
    _write(VALID / "file_read_denied_cross_tenant" / "observation.json", denied_cross)
    _write(VALID / "file_read_denied_cross_tenant" / "event.json", denied_event)

    network = _base_obs(
        observation_id="obs-network-deny-1",
        trace_id="trace-network-deny-1",
        event_id="ev-network-deny-1",
        principal={
            "principal_id": "agent-1",
            "principal_kind": "agent",
            "tenant": "tenant-a",
            "roles": ["agent"],
            "capabilities": [],
        },
        action={
            "action_id": "act-network-1",
            "tool_name": "network.request",
            "capability": {
                "capability_id": "cap:network",
                "effect_kind": "network.egress",
                "resource_pattern": "*",
            },
            "effects": [{"effect_kind": "network.egress"}],
            "reads": [{"resource_id": "res-net", "uri": "https://example.com", "tenant": "tenant-a"}],
            "writes": [],
            "input_hash": "sha256:" + "e" * 64,
            "output_hash": "sha256:" + "f" * 64,
        },
        decision="deny",
        decision_reason="network egress denied",
    )
    network_event = compile_runtime_observation_to_event(network)
    _write(VALID / "network_denied" / "observation.json", network)
    _write(VALID / "network_denied" / "event.json", network_event)

    email = _base_obs(
        observation_id="obs-email-1",
        trace_id="trace-email-1",
        event_id="ev-email-1",
        principal={
            "principal_id": "agent-1",
            "principal_kind": "agent",
            "tenant": "tenant-a",
            "roles": ["agent"],
            "capabilities": ["cap:email-send"],
        },
        action={
            "action_id": "act-email-1",
            "tool_name": "email.send",
            "capability": {
                "capability_id": "cap:email-send",
                "effect_kind": "email.send",
                "resource_pattern": "mailto:*",
            },
            "effects": [{"effect_kind": "email.send"}],
            "reads": [{"resource_id": "res-mail", "uri": "mailto:user@example.com", "tenant": "tenant-a"}],
            "writes": [],
            "input_hash": "sha256:" + "1" * 64,
            "output_hash": "sha256:" + "2" * 64,
        },
    )
    email_event = compile_runtime_observation_to_event(email)
    _write(VALID / "email_send_authorized" / "observation.json", email)
    _write(VALID / "email_send_authorized" / "event.json", email_event)

    handoff = {
        "schema_version": "v0",
        "artifact_type": "PFCoreHandoff.v0",
        "handoff_id": "handoff-subset-1",
        "from_principal": {
            "principal_id": "agent-1",
            "principal_kind": "agent",
            "tenant": "tenant-a",
            "roles": ["agent"],
            "capabilities": ["cap:handoff"],
        },
        "to_principal": {
            "principal_id": "agent-2",
            "principal_kind": "agent",
            "tenant": "tenant-a",
            "roles": ["handoff_delegate"],
            "capabilities": [],
        },
        "delegated_capabilities": [
            {
                "capability_id": "cap:handoff",
                "effect_kind": "handoff.delegate",
                "resource_pattern": "agent:*",
            }
        ],
        "reason": "delegate handoff authority to agent-2",
        "evidence_refs": ["evidence/handoff.v0"],
        "signature_or_digest": GENESIS_HASH,
    }
    payload = {k: v for k, v in handoff.items() if k != "signature_or_digest"}
    handoff["signature_or_digest"] = canonical_hash(payload)
    _write(VALID / "handoff_subset_authority" / "handoff.json", handoff)

    tool_trace = {
        "schema_version": "v0",
        "trace_id": "trace-agent-safety-001",
        "workflow_id": "agent_tool_use.safety_v0",
        "agent_id": "agent-safety-conformance-001",
        "policy_id": "policy-no-secret-exfiltration-v0",
        "policy_hash": "sha256:76d4443f09c6fb0d6cc7bebc5c80eae53bd008e4a212ab61d0d1844ac773b5cd",
        "started_at": "2026-05-18T00:00:00Z",
        "completed_at": "2026-05-18T00:00:05Z",
        "tool_calls": [
            {
                "event_id": "evt-001",
                "timestamp": "2026-05-18T00:00:01Z",
                "tool_name": "filesystem.read",
                "tool_category": "filesystem",
                "input_hash": "sha256:" + "a" * 64,
                "output_hash": "sha256:" + "b" * 64,
                "authorization_status": "authorized",
                "policy_refs": ["policy-no-secret-exfiltration-v0"],
                "resource_uri": "/data/report.txt",
                "tenant": "tenant-a",
            },
            {
                "event_id": "evt-002",
                "timestamp": "2026-05-18T00:00:02Z",
                "tool_name": "network.request",
                "tool_category": "network",
                "input_hash": "sha256:" + "c" * 64,
                "output_hash": "sha256:" + "d" * 64,
                "authorization_status": "rejected",
                "policy_refs": ["policy-no-secret-exfiltration-v0"],
                "resource_uri": "https://example.com",
                "tenant": "tenant-a",
            },
        ],
        "trace_hash": GENESIS_HASH,
        "source_repo": "https://github.com/example/agent-runtime",
        "source_commit": "a111111111111111111111111111111111111111",
        "signature_or_digest": GENESIS_HASH,
    }
    compiled = compile_tool_use_trace_to_pfcore_trace(tool_trace)
    compiled["required_certificate_mode"] = "TraceSafeRCertificate"
    compiled["trace_hash"] = compute_trace_hash(compiled)
    compiled["signature_or_digest"] = compiled["trace_hash"]
    _write(VALID / "tool_use_trace_compiled" / "tool_use_trace.json", tool_trace)
    _write(VALID / "tool_use_trace_compiled" / "pfcore_trace.json", compiled)

    _write(
        INVALID / "unknown_capability" / "manifest.json",
        {
            "expected_error": "UnknownCapability",
            "must_fail_at": "runtime_to_pfcore_event",
        },
    )
    bad_cap = _base_obs(
        action={
            "action_id": "act-bad-cap",
            "tool_name": "filesystem.read",
            "capability": {
                "capability_id": "cap:unknown",
                "effect_kind": "file.read",
                "resource_pattern": "/data/*",
            },
            "effects": [{"effect_kind": "file.read"}],
            "reads": [{"resource_id": "res-1", "uri": "/data/x", "tenant": "tenant-a"}],
            "writes": [],
            "input_hash": "sha256:" + "a" * 64,
            "output_hash": "sha256:" + "b" * 64,
        }
    )
    _write(INVALID / "unknown_capability" / "observation.json", bad_cap)

    _write(
        INVALID / "unknown_effect" / "manifest.json",
        {
            "expected_error": "UnknownEffect",
            "must_fail_at": "runtime_to_pfcore_event",
        },
    )
    bad_effect = _base_obs(
        action={
            "action_id": "act-bad-effect",
            "tool_name": "custom.tool",
            "capability": {
                "capability_id": "cap:file-read",
                "effect_kind": "file.read",
                "resource_pattern": "/data/*",
            },
            "effects": [{"effect_kind": "custom.unknown"}],
            "reads": [{"resource_id": "res-1", "uri": "/data/x", "tenant": "tenant-a"}],
            "writes": [],
            "input_hash": "sha256:" + "a" * 64,
            "output_hash": "sha256:" + "b" * 64,
        }
    )
    _write(INVALID / "unknown_effect" / "observation.json", bad_effect)

    _write(
        INVALID / "missing_principal" / "manifest.json",
        {
            "expected_error": "MissingPrincipal",
            "must_fail_at": "runtime_to_pfcore_event",
        },
    )
    missing_principal = _base_obs(
        principal={
            "principal_id": "",
            "principal_kind": "agent",
            "tenant": "tenant-a",
            "roles": [],
            "capabilities": [],
        }
    )
    _write(INVALID / "missing_principal" / "observation.json", missing_principal)

    tampered_trace = dict(file_read_trace)
    tampered_trace["trace_hash"] = "sha256:" + "f" * 64
    _write(
        INVALID / "trace_hash_mismatch" / "manifest.json",
        {
            "expected_error": "TraceHashMismatch",
            "must_fail_at": "validate_pfcore_trace_hash_chain",
        },
    )
    _write(INVALID / "trace_hash_mismatch" / "trace.json", tampered_trace)

    tampered_event = dict(file_read_event)
    tampered_event["event_hash"] = "sha256:" + "e" * 64
    bad_event_trace = _trace_from_event(
        tampered_event,
        trace_id="trace-bad-event",
        workflow_id="agent_tool_use.safety_v0",
    )
    bad_event_trace["trace_hash"] = "sha256:" + "f" * 64
    _write(
        INVALID / "event_hash_mismatch" / "manifest.json",
        {
            "expected_error": "EventHashMismatch",
            "must_fail_at": "validate_pfcore_trace_hash_chain",
        },
    )
    _write(INVALID / "event_hash_mismatch" / "trace.json", bad_event_trace)

    _write(
        INVALID / "dropped_denied_event" / "manifest.json",
        {
            "expected_error": "DroppedDeniedEvent",
            "must_fail_at": "validate_denied_events_preserved",
        },
    )
    dropped_tool = {
        "schema_version": "v0",
        "trace_id": "trace-dropped-deny",
        "workflow_id": "agent_tool_use.safety_v0",
        "agent_id": "agent-1",
        "policy_id": "policy/default.v0",
        "policy_hash": GENESIS_HASH,
        "started_at": "2026-06-18T00:00:00Z",
        "completed_at": "2026-06-18T00:00:01Z",
        "tool_calls": [
            {
                "event_id": "evt-deny",
                "timestamp": "2026-06-18T00:00:01Z",
                "tool_name": "network.request",
                "tool_category": "network",
                "input_hash": "sha256:" + "a" * 64,
                "output_hash": "sha256:" + "b" * 64,
                "authorization_status": "rejected",
                "policy_refs": ["policy/default.v0"],
                "tenant": "tenant-a",
            }
        ],
        "trace_hash": GENESIS_HASH,
        "source_repo": "https://github.com/example/agent-runtime",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": GENESIS_HASH,
    }
    dropped_compiled = compile_tool_use_trace_to_pfcore_trace(dropped_tool)
    dropped_compiled["events"] = [
        event for event in dropped_compiled["events"] if event["decision"] != "deny"
    ]
    _write(INVALID / "dropped_denied_event" / "tool_use_trace.json", dropped_tool)
    _write(INVALID / "dropped_denied_event" / "pfcore_trace.json", dropped_compiled)

    _write(
        INVALID / "handoff_authority_expansion" / "manifest.json",
        {
            "expected_error": "HandoffAuthorityExpansion",
            "must_fail_at": "validate_handoff_authority",
        },
    )
    bad_handoff = {
        "schema_version": "v0",
        "artifact_type": "PFCoreHandoff.v0",
        "handoff_id": "handoff-bad-1",
        "from_principal": {
            "principal_id": "agent-1",
            "principal_kind": "agent",
            "tenant": "tenant-a",
            "roles": ["file_reader"],
            "capabilities": [],
        },
        "to_principal": {
            "principal_id": "agent-2",
            "principal_kind": "agent",
            "tenant": "tenant-a",
            "roles": ["handoff_delegate"],
            "capabilities": [],
        },
        "delegated_capabilities": [
            {
                "capability_id": "cap:network",
                "effect_kind": "network.egress",
                "resource_pattern": "*",
            }
        ],
        "reason": "over-delegation",
        "evidence_refs": [],
        "signature_or_digest": GENESIS_HASH,
    }
    _write(INVALID / "handoff_authority_expansion" / "handoff.json", bad_handoff)

    overclaim_trace = dict(file_read_trace)
    overclaim_trace["claim_class"] = "LeanKernelChecked"
    _write(
        INVALID / "claim_class_overclaim" / "manifest.json",
        {
            "expected_error": "ClaimClassOverclaim",
            "must_fail_at": "validate_pfcore_trace_hash_chain",
        },
    )
    _write(INVALID / "claim_class_overclaim" / "trace.json", overclaim_trace)


if __name__ == "__main__":
    main()
    print(f"Wrote fixtures under {ROOT}")
