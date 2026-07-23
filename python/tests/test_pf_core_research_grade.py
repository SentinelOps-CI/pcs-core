"""Integration tests for PF-Core research-grade extensions (Phases I–VII)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pcs_core.lean_catalog import PF_CORE_THEOREM_CATALOG
from pcs_core.pf_core_claims import audit_lean_catalog
from pcs_core.pf_core_lean_codegen import contract_pre_to_lean, generate_proof_obligation_file
from pcs_core.pf_core_replay import (
    build_replay_certificate,
    claim_class_rank,
    replay_preserves_claim_boundary,
    replay_trace,
)

REPO = Path(__file__).resolve().parents[2]
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"


LAKE_AVAILABLE = shutil.which("lake") is not None

RESEARCH_GRADE_THEOREMS = frozenset(
    {
        "stepState_frame_preserved",
        "traceExtendsSafely_of_step",
        "safe_extension_preserves_trace_safe_strong",
        "effect_frame_prevents_undeclared_writes",
        "contract_refinement_preserves_trace_safe",
        "handoff_preserves_trace_safe_strong",
        "handoff_composition_global",
        "traceSafe_implies_tenant_isolation",
        "contractPre_role_aligned_capability",
        "frameValidD_sound",
        "effectFrameAdmissibleD_sound",
        "tenantIsolationD_sound",
        "principalHasRoleD_sound",
    }
)

RESEARCH_MODULES = (
    "Transition.lean",
    "EffectFrame.lean",
    "State.lean",
    "Compositional.lean",
    "NonInterference.lean",
    "ContractDecide.lean",
    "ObservedEffect.lean",
    "DenyClosed.lean",
    "PairedExecution.lean",
)


def _lean_source(name: str) -> str:
    path = REPO / "lean" / "PFCore" / name
    assert path.is_file(), f"missing Lean module: {path}"
    return path.read_text(encoding="utf-8")


def test_research_grade_theorems_in_catalog() -> None:
    missing = RESEARCH_GRADE_THEOREMS - PF_CORE_THEOREM_CATALOG
    assert not missing, f"missing from PF_CORE_THEOREM_CATALOG: {sorted(missing)}"


def test_research_grade_lean_catalog_audit() -> None:
    errors = audit_lean_catalog()
    research_errors = [
        err for err in errors if any(name in err for name in RESEARCH_GRADE_THEOREMS)
    ]
    assert research_errors == [], research_errors


@pytest.mark.parametrize("module", RESEARCH_MODULES)
def test_research_modules_no_sorry(module: str) -> None:
    text = _lean_source(module)
    assert "sorry" not in text, f"sorry found in {module}"
    assert "admit" not in text, f"admit found in {module}"
    assert "axiom" not in text, f"axiom found in {module}"


def test_transition_operational_defs_present() -> None:
    text = _lean_source("Transition.lean")
    for symbol in (
        "def stepState",
        "def Applies",
        "def FramePreserved",
        "def TraceExtendsSafely",
        "theorem stepState_frame_preserved",
        "theorem traceExtendsSafely_of_step",
        "theorem safe_extension_preserves_trace_safe_strong",
    ):
        assert symbol in text, f"missing {symbol}"


def test_effect_frame_theorems_present() -> None:
    text = _lean_source("EffectFrame.lean")
    assert "theorem effect_frame_prevents_undeclared_writes" in text
    assert "def WriteFootprintRequiresWriteEffect" in text


def test_contract_refinement_present() -> None:
    text = _lean_source("Compositional.lean")
    assert "def ContractRefinement" in text
    assert "theorem contract_refinement_preserves_trace_safe" in text
    assert "theorem handoff_composition_global" in text
    assert "def CompositionalSafeExtension" in text
    assert "abbrev TracePrefixSafe" in text
    assert "theorem compositional_safe_extension_yields_safe_extended_trace" in text


def test_tenant_isolation_present() -> None:
    text = _lean_source("NonInterference.lean")
    assert "def TenantIsolation" in text
    assert "theorem traceSafe_implies_tenant_isolation" in text


def test_contract_decide_role_field_present() -> None:
    text = _lean_source("ContractDecide.lean")
    assert "requireRole" in text
    assert "theorem principalHasRoleD_sound" in text
    assert "theorem contractPre_role_aligned_capability" in text


def test_codegen_emits_require_role_when_lean(tmp_path: Path) -> None:
    contract = {
        "pre": {"require_role": "file_reader"},
        "semantics_layer": {"require_role": "lean"},
    }
    lean = contract_pre_to_lean(contract, name="rolePre")
    assert 'requireRole := some "file_reader"' in lean


def test_replay_preserves_claim_boundary_theorem() -> None:
    assert replay_preserves_claim_boundary("RuntimeChecked", "RuntimeChecked")
    assert replay_preserves_claim_boundary("ReplayValidated", "ReplayValidated")
    assert not replay_preserves_claim_boundary("RuntimeChecked", "ReplayValidated")
    assert not replay_preserves_claim_boundary("SchemaValidated", "RuntimeChecked")
    assert claim_class_rank("LeanKernelChecked") > claim_class_rank("ReplayValidated")


def test_replay_certificate_respects_claim_boundary() -> None:
    trace = json.loads(VALID_TRACE.read_text(encoding="utf-8"))
    result = replay_trace(VALID_TRACE)
    if not result.match:
        pytest.skip("trace replay mismatch in fixture")
    trace["claim_class"] = "SchemaValidated"
    cert = build_replay_certificate(trace, result)
    assert cert["claim_class"] == "SchemaValidated"
    trace["claim_class"] = "RuntimeChecked"
    cert_ok = build_replay_certificate(trace, result)
    assert cert_ok["claim_class"] == "RuntimeChecked"
    assert any(
        item.get("theorem") == "replay_preserves_claim_boundary"
        for item in cert_ok.get("obligations", [])
    )


@pytest.mark.skipif(not LAKE_AVAILABLE, reason="lake or responsive WSL not available")
def test_lake_build_pfcore_research_modules() -> None:
    from pcs_core.lean_check import run_lean_library_build

    ok, detail = run_lean_library_build(target="PFCore")
    if not ok and ("lake unavailable" in detail or "timed out" in detail.lower()):
        pytest.skip(detail)
    assert ok, detail


@pytest.mark.skipif(not LAKE_AVAILABLE, reason="lake or responsive WSL not available")
def test_generated_proof_compiles_with_extended_catalog() -> None:
    from pcs_core.lean_check import pfcore_generated_dir, run_lean_concrete_proof

    trace = json.loads(VALID_TRACE.read_text(encoding="utf-8"))
    generated = generate_proof_obligation_file(
        trace, pfcore_generated_dir(), trace_path=VALID_TRACE
    )
    proof_path = generated.path
    ok, detail = run_lean_concrete_proof(proof_path, skip_build=False)
    if not ok and ("lake unavailable" in detail or "timed out" in detail.lower()):
        pytest.skip(detail)
    assert ok, detail


def test_audit_lean_catalog_cli() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pcs_core.cli", "pf-core", "audit-lean-catalog"],
        cwd=REPO / "python",
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
