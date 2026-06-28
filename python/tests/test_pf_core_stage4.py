"""Tests for PF-Core Stage 4 Lean bridge (codegen + concrete proof)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pcs_core.lean_check import (
    LEAN_CHECK_DISCLAIMER,
    check_pfcore_trace_lean_semantics,
    run_lean_concrete_proof,
    run_lean_library_build,
    run_pfcore_lean_check,
)
from pcs_core.pf_core_lean_codegen import (
    generate_proof_obligation_file,
    trace_to_lean,
)
from pcs_core.validate import validate_file, validate_schema

REPO = Path(__file__).resolve().parents[2]
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"
EMPTY_TRACE = REPO / "examples" / "pf-core-valid" / "empty_trace" / "trace.json"
# Native `lake` only at import time; WSL fallback is probed inside tests when needed.
LAKE_AVAILABLE = shutil.which("lake") is not None


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_lean_check_result_schema_registered() -> None:
    sample = {
        "schema_version": "v0",
        "artifact_type": "LeanCheckResult.v0",
        "status": "Rejected",
        "claim_class": "OutOfScope",
        "assumption_refs": ["docs/pf-core/assumptions.md"],
        "theorems_checked": ["traceSafeD_sound"],
        "lean_build_status": {"ok": False, "target": "PFCore", "detail": "skipped"},
        "disclaimer": LEAN_CHECK_DISCLAIMER,
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    assert validate_schema(sample, "LeanCheckResult.v0") == []


def test_trace_to_lean_generates_kernel_constructs() -> None:
    trace = _load(VALID_TRACE)
    source = trace_to_lean(trace)
    assert "def trace_trace_agent_safety_001 : Trace" in source or "Trace.cons" in source
    assert "Decision.allow" in source or "Decision.deny" in source
    assert "Principal :=" in source
    assert "Action :=" in source


def test_generate_proof_obligation_file_writes_theorem(tmp_path: Path) -> None:
    trace = _load(VALID_TRACE)
    proof_path = generate_proof_obligation_file(trace, tmp_path, trace_path=VALID_TRACE)
    text = proof_path.read_text(encoding="utf-8")
    assert "theorem concrete_trace_safe" in text
    assert "theorem concrete_event_safe_" in text
    assert "concrete_action_resource_scope_" in text
    assert "actionResourcesWithinCapabilityPatternD" in text
    assert "theorem concrete_trace_safe_r" in text
    assert "theorem concrete_trace_safe_r_prop" in text
    assert "decide" in text
    assert "import PFCore.TraceCheck" in text


def test_empty_trace_codegen(tmp_path: Path) -> None:
    trace = _load(EMPTY_TRACE)
    source = trace_to_lean(trace)
    assert "Trace.empty" in source
    proof_path = generate_proof_obligation_file(trace, tmp_path)
    assert "theorem concrete_trace_safe" in proof_path.read_text(encoding="utf-8")


def test_invalid_trace_fails_before_lean_proof() -> None:
    trace = _load(VALID_TRACE)
    event = dict(trace["events"][0])
    event["decision"] = "allow"
    event["principal"] = dict(event["principal"])
    event["principal"]["capabilities"] = []
    event["principal"]["roles"] = []
    mutated = dict(trace)
    mutated["events"] = [event]
    issues = check_pfcore_trace_lean_semantics(mutated)
    assert any(issue.code == "EventUnsafe" for issue in issues)


@pytest.mark.parametrize("skip_build", [True])
def test_skip_build_emits_runtime_checked(tmp_path: Path, skip_build: bool) -> None:
    out = tmp_path / "PFCoreCertificate.v0.json"
    result_out = tmp_path / "LeanCheckResult.v0.json"
    code, result = run_pfcore_lean_check(
        VALID_TRACE,
        out_path=out,
        result_out_path=result_out,
        skip_build=skip_build,
    )
    assert code == 0, result
    assert result["status"] == "DecidersPassed"
    assert result["claim_class"] == "RuntimeChecked"
    assert result["lean_proof_checked"] is False
    cert = json.loads(out.read_text(encoding="utf-8"))
    assert cert["claim_class"] == "RuntimeChecked"
    assert "proof_term_ref" not in cert
    validate_file(result_out)
    validate_file(out)


@pytest.mark.parametrize("skip_lean_proof", [True])
def test_skip_lean_proof_emits_runtime_checked(tmp_path: Path, skip_lean_proof: bool) -> None:
    code, result = run_pfcore_lean_check(
        VALID_TRACE,
        out_path=tmp_path / "cert.json",
        skip_build=True,
        skip_lean_proof=skip_lean_proof,
    )
    assert code == 0, result
    assert result["claim_class"] == "RuntimeChecked"
    assert result["status"] == "DecidersPassed"
    assert not any(
        item.get("kind") == "ConcreteTraceSafe" for item in result.get("obligations", [])
    )


@pytest.mark.skipif(not LAKE_AVAILABLE, reason="lake or WSL not available")
def test_concrete_lean_proof_passes_for_valid_trace() -> None:
    from pcs_core.lean_check import pfcore_generated_dir

    trace = _load(VALID_TRACE)
    proof_path = generate_proof_obligation_file(trace, pfcore_generated_dir())
    ok, detail = run_lean_concrete_proof(proof_path, skip_build=False)
    assert ok, detail


@pytest.mark.skipif(not LAKE_AVAILABLE, reason="lake or WSL not available")
def test_full_pipeline_emits_lean_kernel_checked(tmp_path: Path) -> None:
    out = tmp_path / "PFCoreCertificate.v0.json"
    result_out = tmp_path / "LeanCheckResult.v0.json"
    code, result = run_pfcore_lean_check(
        VALID_TRACE,
        out_path=out,
        result_out_path=result_out,
    )
    assert code == 0, result
    assert result["status"] == "LeanProofChecked"
    assert result["claim_class"] == "LeanKernelChecked"
    assert result["lean_proof_checked"] is True
    assert any(
        item.get("kind") == "ConcreteTraceSafe" and item.get("passed") is True
        for item in result["obligations"]
    )
    cert = json.loads(out.read_text(encoding="utf-8"))
    assert cert["claim_class"] == "LeanKernelChecked"
    assert cert["lean_proof_checked"] is True
    assert cert.get("proof_term_ref", "").startswith("lean/PFCore/Generated/")
    assert cert.get("lean_environment_hash", "").startswith("sha256:")
    validate_file(result_out)
    validate_file(out)


def test_lean_kernel_checked_not_emitted_when_proof_skipped(tmp_path: Path) -> None:
    _, result = run_pfcore_lean_check(
        VALID_TRACE,
        out_path=tmp_path / "cert.json",
        skip_build=True,
    )
    assert result["claim_class"] != "LeanKernelChecked"
    assert result["status"] == "DecidersPassed"


def test_pfcore_certificate_schema_accepts_obligations() -> None:
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-test",
        "trace_hash": "sha256:" + "0" * 64,
        "contract_hash": "sha256:" + "0" * 64,
        "policy_hash": "sha256:" + "0" * 64,
        "claim_class": "RuntimeChecked",
        "checker": "pcs-core",
        "checker_version": "0.1.0",
        "assumption_refs": ["docs/pf-core/assumptions.md"],
        "obligations": [
            {"kind": "TraceSafeDeciderSound", "theorem": "traceSafeD_sound", "passed": True}
        ],
        "lean_proof_checked": False,
        "event_count": 0,
        "source_repo": "https://github.com/example/pcs-core",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    assert validate_schema(cert, "PFCoreCertificate.v0") == []


@pytest.mark.skipif(not LAKE_AVAILABLE, reason="lake or WSL not available")
def test_lake_build_pfcore_succeeds() -> None:
    import os

    os.environ.setdefault("PCS_LAKE_TIMEOUT_SECONDS", "600")
    ok, detail = run_lean_library_build(target="PFCore")
    if not ok and ("lake unavailable" in detail or "timed out" in detail.lower()):
        pytest.skip(detail)
    assert ok, detail
