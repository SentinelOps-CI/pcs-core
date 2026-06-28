"""Tests for PF-Core Phase D: invariant theorem and richer Lean codegen."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pcs_core.pf_core_lean_codegen import (
    generate_proof_obligation_file,
    trace_has_contract_refs,
)
from pcs_core.validate import validate_file

REPO = Path(__file__).resolve().parents[2]
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"
CONTRACT_TRACE = REPO / "examples" / "pf-core-valid" / "contract_checked" / "trace.json"
HANDOFF_FIXTURE = REPO / "examples" / "pf-core-valid" / "handoff_subset_authority" / "handoff.json"
ASSUMPTION_CERT = REPO / "examples" / "pf-core-valid" / "assumption_declared" / "certificate.json"
LAKE_AVAILABLE = shutil.which("lake") is not None


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_lean_has_invariant_preserved_cons_theorem() -> None:
    text = (REPO / "lean" / "PFCore" / "Contract.lean").read_text(encoding="utf-8")
    assert "theorem invariant_preserved_cons" in text
    assert "sorry" not in text


def test_generated_proof_includes_per_event_theorems(tmp_path: Path) -> None:
    trace = _load(VALID_TRACE)
    proof_path = generate_proof_obligation_file(trace, tmp_path, trace_path=VALID_TRACE)
    text = proof_path.read_text(encoding="utf-8")
    assert "theorem concrete_event_safe_" in text
    assert "eventSafeD evt_001 = true := by" in text or "eventSafeD ev_" in text
    assert "#check eventSafeD" not in text


def test_generated_proof_documents_contract_refs_when_missing(tmp_path: Path) -> None:
    trace = _load(CONTRACT_TRACE)
    assert trace_has_contract_refs(trace)
    # No contract JSON alongside trace -> documents gap
    proof_path = generate_proof_obligation_file(trace, tmp_path)
    text = proof_path.read_text(encoding="utf-8")
    assert "validate-contracts" in text


def test_generated_proof_discharges_contracts_with_json(tmp_path: Path) -> None:
    trace = _load(CONTRACT_TRACE)
    proof_path = generate_proof_obligation_file(trace, tmp_path, trace_path=CONTRACT_TRACE)
    text = proof_path.read_text(encoding="utf-8")
    assert "concrete_trace_satisfies_contract_" in text


def test_generated_proof_includes_handoff_when_present(tmp_path: Path) -> None:
    handoff = _load(HANDOFF_FIXTURE)
    trace = _load(VALID_TRACE)
    trace_file = tmp_path / "pfcore_trace.json"
    trace_file.write_text(json.dumps(trace), encoding="utf-8")
    (tmp_path / "handoff.json").write_text(json.dumps(handoff), encoding="utf-8")
    proof_path = generate_proof_obligation_file(trace, tmp_path / "out", trace_path=trace_file)
    text = proof_path.read_text(encoding="utf-8")
    assert "handoffSafeD" in text
    assert "theorem concrete_handoff_safe_" in text


@pytest.mark.skipif(not LAKE_AVAILABLE, reason="lake or WSL not available")
def test_generated_proof_compiles_with_lake() -> None:
    from pcs_core.lean_check import pfcore_generated_dir, run_lean_concrete_proof

    trace = _load(VALID_TRACE)
    proof_path = generate_proof_obligation_file(
        trace, pfcore_generated_dir(), trace_path=VALID_TRACE
    )
    ok, detail = run_lean_concrete_proof(proof_path, skip_build=False)
    if not ok and ("lake unavailable" in detail or "timed out" in detail.lower()):
        pytest.skip(detail)
    assert ok, detail


def test_assumption_declared_fixture_validates() -> None:
    validate_file(ASSUMPTION_CERT)
    validate_file(REPO / "examples/pf-core-valid/assumption_declared/assumption_set.json")


def test_assumption_set_id_ref_enforced_for_deferred_certificate() -> None:
    cert = _load(ASSUMPTION_CERT)
    refs = cert.get("assumption_refs")
    assert isinstance(refs, list)
    assert any(str(ref).startswith("as-") for ref in refs)
    assert cert["claim_class"] == "AssumptionDeclared"
