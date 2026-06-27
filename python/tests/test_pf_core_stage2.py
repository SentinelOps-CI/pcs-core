"""Tests for PF-Core Stage 2 schemas, compiler, and fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.pf_core_claims import audit_boundary
from pcs_core.pf_core_runtime import (
    ClaimClassOverclaim,
    DroppedDeniedEvent,
    HandoffAuthorityExpansion,
    MissingPrincipal,
    UnknownCapability,
    UnknownEffect,
    compile_runtime_observation_to_event,
    compile_tool_use_trace_to_pfcore_trace,
    validate_denied_events_preserved,
    validate_handoff_authority,
    validate_pfcore_trace_hash_chain,
)
from pcs_core.registry_data import pf_core_artifact_types, registry_entries
from pcs_core.validate import (
    ARTIFACT_SCHEMAS,
    ValidationError,
    check_all_schemas,
    detect_artifact_type,
    load_pf_core_fixture_manifest,
    validate_artifact,
    validate_file,
)

REPO = Path(__file__).resolve().parents[2]
VALID = REPO / "examples" / "pf-core-valid"
INVALID = REPO / "examples" / "pf-core-invalid"

PF_CORE_SCHEMA_TYPES = [
    "PFCorePrincipal.v0",
    "PFCoreCapability.v0",
    "PFCoreResource.v0",
    "PFCoreAction.v0",
    "PFCoreEffect.v0",
    "PFCoreDecision.v0",
    "PFCoreEvent.v0",
    "PFCoreTrace.v0",
    "PFCoreContract.v0",
    "PFCoreHandoff.v0",
    "PFCoreRuntimeObservation.v0",
    "PFCoreCertificate.v0",
]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("artifact_type", PF_CORE_SCHEMA_TYPES)
def test_pf_core_schema_registered(artifact_type: str) -> None:
    assert artifact_type in ARTIFACT_SCHEMAS


def test_all_schemas_compile() -> None:
    check_all_schemas()


@pytest.mark.parametrize("case_dir", sorted(VALID.iterdir()) if VALID.is_dir() else [])
def test_valid_pf_core_fixtures(case_dir: Path) -> None:
    for path in sorted(case_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        if path.name == "tool_use_trace.json" and (case_dir / "pfcore_trace.json").is_file():
            continue
        data = _load(path)
        artifact_type = detect_artifact_type(data)
        assert artifact_type is not None, f"Could not detect type for {path}"
        validate_artifact(data, artifact_type)


@pytest.mark.parametrize("case_dir", sorted(INVALID.iterdir()) if INVALID.is_dir() else [])
def test_invalid_pf_core_fixtures(case_dir: Path) -> None:
    manifest = load_pf_core_fixture_manifest(case_dir)
    expected_error = manifest["expected_error"]
    must_fail_at = manifest["must_fail_at"]

    if must_fail_at == "runtime_to_pfcore_event":
        observation = _load(case_dir / "observation.json")
        with pytest.raises((UnknownCapability, UnknownEffect, MissingPrincipal)) as exc:
            compile_runtime_observation_to_event(observation)
        assert exc.value.code == expected_error
        return

    if must_fail_at == "validate_pfcore_trace_hash_chain":
        trace = _load(case_dir / "trace.json")
        errors = validate_pfcore_trace_hash_chain(trace)
        assert any(expected_error in err for err in errors)
        return

    if must_fail_at == "validate_denied_events_preserved":
        tool_use_trace = _load(case_dir / "tool_use_trace.json")
        pfcore_trace = _load(case_dir / "pfcore_trace.json")
        with pytest.raises(DroppedDeniedEvent) as exc:
            validate_denied_events_preserved(tool_use_trace, pfcore_trace)
        assert exc.value.code == expected_error
        return

    if must_fail_at == "validate_handoff_authority":
        handoff = _load(case_dir / "handoff.json")
        with pytest.raises(HandoffAuthorityExpansion) as exc:
            validate_handoff_authority(handoff)
        assert exc.value.code == expected_error
        return

    if must_fail_at == "compile_tool_use_trace_to_pfcore_trace":
        tool_use_trace = _load(case_dir / "tool_use_trace.json")
        with pytest.raises(HandoffAuthorityExpansion) as exc:
            compile_tool_use_trace_to_pfcore_trace(tool_use_trace)
        assert exc.value.code == expected_error
        return

    if must_fail_at == "validate_trace_contracts":
        from pcs_core.pf_core_contract import validate_trace_contracts

        trace = _load(case_dir / "trace.json")
        contracts = {
            str(data["contract_id"]): data
            for data in (
                _load(path) for path in sorted((case_dir / "contracts").glob("*.json"))
            )
        }
        issues = validate_trace_contracts(trace, contracts)
        assert any(issue.code == expected_error for issue in issues)
        return

    if must_fail_at == "validate_tenant_isolation":
        from pcs_core.pf_core_runtime import validate_tenant_isolation

        trace = _load(case_dir / "trace.json")
        errors = validate_tenant_isolation(trace)
        assert any(expected_error in err for err in errors)
        return

    pytest.fail(f"Unknown must_fail_at {must_fail_at!r} in {case_dir}")


def test_tool_use_trace_compiles_to_pfcore_trace() -> None:
    tool_use_trace = _load(VALID / "tool_use_trace_compiled" / "tool_use_trace.json")
    expected = _load(VALID / "tool_use_trace_compiled" / "pfcore_trace.json")
    compiled = compile_tool_use_trace_to_pfcore_trace(tool_use_trace)
    assert compiled["artifact_type"] == "PFCoreTrace.v0"
    assert len(compiled["events"]) == len(tool_use_trace["tool_calls"])
    assert compiled["trace_hash"] == expected["trace_hash"]
    denied = [event for event in compiled["events"] if event["decision"] == "deny"]
    assert len(denied) == 1
    assert denied[0]["event_id"] == "evt-002"


def test_denied_events_preserved_in_compilation() -> None:
    tool_use_trace = _load(VALID / "tool_use_trace_compiled" / "tool_use_trace.json")
    compiled = compile_tool_use_trace_to_pfcore_trace(tool_use_trace)
    validate_denied_events_preserved(tool_use_trace, compiled)


def test_trace_hash_chain_validation_passes_for_valid_trace() -> None:
    trace = _load(VALID / "file_read_allowed" / "trace.json")
    assert validate_pfcore_trace_hash_chain(trace) == []


def test_explicit_artifact_type_detection_pfcore() -> None:
    data = {"artifact_type": "PFCoreTrace.v0", "trace_id": "t-1"}
    assert detect_artifact_type(data) == "PFCoreTrace.v0"


def test_registry_audit_includes_pf_core_entries() -> None:
    assert audit_boundary() == []
    entries = registry_entries()
    for artifact_type in pf_core_artifact_types():
        assert artifact_type in entries
        assert artifact_type in ARTIFACT_SCHEMAS


def test_compile_runtime_observation_produces_event() -> None:
    observation = _load(VALID / "file_read_allowed" / "observation.json")
    event = compile_runtime_observation_to_event(observation)
    assert event["artifact_type"] == "PFCoreEvent.v0"
    assert event["decision"] == "allow"
    assert validate_pfcore_trace_hash_chain({"events": [event]}) == []


def test_cross_tenant_allow_becomes_deny() -> None:
    observation = _load(VALID / "file_read_denied_cross_tenant" / "observation.json")
    event = compile_runtime_observation_to_event(observation)
    assert event["decision"] == "deny"


def test_claim_class_overclaim_in_semantic_validation() -> None:
    trace = _load(INVALID / "claim_class_overclaim" / "trace.json")
    with pytest.raises(ValidationError) as exc:
        validate_artifact(trace, "PFCoreTrace.v0")
    assert any("ClaimClassOverclaim" in err for err in exc.value.errors)


def test_handoff_subset_authority_valid() -> None:
    handoff = _load(VALID / "handoff_subset_authority" / "handoff.json")
    validate_handoff_authority(handoff)


def test_network_denied_event_decision() -> None:
    event = _load(VALID / "network_denied" / "event.json")
    assert event["decision"] == "deny"


def test_claim_class_overclaim_raises() -> None:
    with pytest.raises(ClaimClassOverclaim):
        from pcs_core.pf_core_runtime import _assert_claim_class_allowed

        _assert_claim_class_allowed("LeanKernelChecked")
