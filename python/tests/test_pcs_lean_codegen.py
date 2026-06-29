"""Tests for PCS per-obligation Lean codegen."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pcs_core.lean_trust import extract_proof_obligations_from_release, run_lean_check
from pcs_core.paths import examples_dir, repo_root
from pcs_core.pcs_lean_codegen import (
    aggregate_lean_theorem_for_workflow,
    computation_values_from_obligations,
    generate_from_release_dir,
    generate_proof_obligation_file,
    generated_module_name,
    release_chain_values_from_obligations,
    tool_use_values_from_obligations,
)
from pcs_core.validate import validate_file

LABTRUST = examples_dir() / "labtrust-release"
TOOL_USE = examples_dir() / "tool-use-release"
COMPUTATION = examples_dir() / "computation-release"


def test_release_chain_values_from_labtrust_obligations() -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    values = release_chain_values_from_obligations(doc)
    assert values["certificate_status"] == "CertificateChecked"
    assert values["certificate_trace_hash"] == values["runtime_trace_hash"]
    assert values["signed_input_bundle_hash"] == values["verified_input_bundle_hash"]


def test_generate_proof_obligation_file_writes_theorems(tmp_path: Path) -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    path = generate_proof_obligation_file(doc, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "concrete_release_chain_admissible" in text
    assert "concrete_certificate_matches_runtime_prop" in text
    assert "concrete_verification_admits_bundle_prop" in text
    assert "concrete_signed_bundle_admissible_prop" in text
    assert "releaseChainAdmissibleD" in text
    assert "ReleaseChainAdmissible" in text
    assert generated_module_name(doc) in text


def test_run_lean_check_envelope_proof_class_without_build() -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    result = run_lean_check(doc, require_lean_build=False, lean_proof=False)
    assert result["status"] == "ProofChecked"
    assert result["claim_class"] == "ProofChecked"
    assert result.get("lean_proof_checked") is False


@pytest.mark.skipif(
    shutil.which("lake") is None,
    reason="lake executable not on PATH",
)
def test_pcs_envelope_lean_proof_on_labtrust_fixture(tmp_path: Path) -> None:
    doc = extract_proof_obligations_from_release(LABTRUST)
    out = tmp_path / "lean_check_result.v0.json"
    result = run_lean_check(doc, require_lean_build=True, lean_proof=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    validate_file(out)
    assert result["status"] == "ProofChecked"
    assert result["claim_class"] == "EnvelopeLeanChecked"
    assert result["lean_proof_checked"] is True
    assert result.get("proof_term_ref")


def test_generate_from_release_dir_matches_committed_fixture() -> None:
    generated = repo_root() / "lean" / "PCS" / "Generated"
    path = generate_from_release_dir(LABTRUST, generated)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "concrete_release_chain_admissible_prop" in text
    assert "concrete_certificate_matches_runtime_prop" in text
    assert "concrete_verification_admits_bundle_prop" in text
    assert "concrete_signed_bundle_admissible_prop" in text


def test_tool_use_values_from_obligations() -> None:
    doc = extract_proof_obligations_from_release(TOOL_USE)
    values = tool_use_values_from_obligations(doc)
    assert values["trace_hash"] == values["certificate_trace_hash"]
    assert values["policy_hash"] == values["tool_certificate_policy_hash"]


def test_computation_values_from_obligations() -> None:
    doc = extract_proof_obligations_from_release(COMPUTATION)
    values = computation_values_from_obligations(doc)
    assert values["result_artifact_sha256"] in values["witness_result_hashes"]


def test_generate_tool_use_proof_file(tmp_path: Path) -> None:
    doc = extract_proof_obligations_from_release(TOOL_USE)
    path = generate_proof_obligation_file(doc, tmp_path, release_dir=TOOL_USE)
    text = path.read_text(encoding="utf-8")
    assert "concrete_tool_trace_hash_matches_prop" in text
    assert "concrete_tool_use_release_admissible_prop" in text
    assert aggregate_lean_theorem_for_workflow(doc["workflow_id"]) == (
        "concrete_tool_use_release_admissible_prop"
    )


def test_generate_computation_proof_file(tmp_path: Path) -> None:
    doc = extract_proof_obligations_from_release(COMPUTATION)
    path = generate_proof_obligation_file(doc, tmp_path, release_dir=COMPUTATION)
    text = path.read_text(encoding="utf-8")
    assert "concrete_witness_result_hashes_admissible_prop" in text
    assert "concrete_witness_result_hash_listed_prop" in text
    assert "concrete_computation_release_admissible_prop" in text


@pytest.mark.skipif(
    shutil.which("lake") is None,
    reason="lake executable not on PATH",
)
def test_pcs_envelope_lean_proof_on_tool_use_fixture(tmp_path: Path) -> None:
    doc = extract_proof_obligations_from_release(TOOL_USE)
    result = run_lean_check(doc, require_lean_build=True, lean_proof=True)
    assert result["status"] == "ProofChecked"
    assert result["claim_class"] == "EnvelopeLeanChecked"
    assert result.get("proof_term_ref")
    assert any(
        item.get("lean_theorem") == "concrete_tool_use_release_admissible_prop"
        for item in result.get("obligation_results") or []
        if isinstance(item, dict)
    )
