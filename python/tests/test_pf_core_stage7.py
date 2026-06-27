"""Tests for PF-Core Stage 7 semantic depth (contracts, handoff, resource scope)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.pf_core_contract import load_contract, validate_trace_contracts
from pcs_core.pf_core_replay import replay_trace
from pcs_core.pf_core_runtime import (
    HandoffAuthorityExpansion,
    compile_tool_use_trace_to_pfcore_trace,
    validate_pfcore_trace_hash_chain,
)
from pcs_core.validate import check_pf_core_valid_fixtures, validate_file

REPO = Path(__file__).resolve().parents[2]
CONTRACT_VALID = REPO / "examples" / "pf-core-valid" / "contract_checked"
CONTRACT_INVALID = REPO / "examples" / "pf-core-invalid" / "contract_violation"
RESOURCE_INVALID = REPO / "examples" / "pf-core-invalid" / "resource_scope_violation"
HANDOFF_COMPILE_INVALID = REPO / "examples" / "pf-core-invalid" / "handoff_compile_expansion"
LABTRUST_REPLAY = REPO / "examples" / "pf-core-valid" / "labtrust_replay" / "trace.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_checked_fixture_validates() -> None:
    validate_file(CONTRACT_VALID / "contract.json")
    validate_file(CONTRACT_VALID / "trace.json")


def test_contract_satisfaction_passes_for_valid_fixture() -> None:
    trace = _load(CONTRACT_VALID / "trace.json")
    contract = load_contract(CONTRACT_VALID / "contract.json")
    issues = validate_trace_contracts(trace, {contract["contract_id"]: contract})
    assert issues == []


def test_contract_violation_detected() -> None:
    trace = _load(CONTRACT_INVALID / "trace.json")
    contract = load_contract(CONTRACT_INVALID / "contracts" / "contract.json")
    issues = validate_trace_contracts(trace, {contract["contract_id"]: contract})
    assert any(issue.code == "ContractDecisionMismatch" for issue in issues)


def test_resource_scope_violation_detected() -> None:
    trace = _load(RESOURCE_INVALID / "trace.json")
    errors = validate_pfcore_trace_hash_chain(trace)
    assert any("ResourceScopeViolation" in err for err in errors)


def test_handoff_compile_expansion_rejected() -> None:
    tool_use = _load(HANDOFF_COMPILE_INVALID / "tool_use_trace.json")
    with pytest.raises(HandoffAuthorityExpansion):
        compile_tool_use_trace_to_pfcore_trace(tool_use)


def test_labtrust_replay_fixture_in_examples_check() -> None:
    check_pf_core_valid_fixtures()
    result = replay_trace(LABTRUST_REPLAY)
    assert result.match is True
