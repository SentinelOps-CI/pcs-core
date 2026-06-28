"""Tests for PCS per-obligation Lean codegen."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pcs_core.lean_trust import extract_proof_obligations_from_release, run_lean_check
from pcs_core.paths import examples_dir, repo_root
from pcs_core.pcs_lean_codegen import (
    generate_from_release_dir,
    generate_proof_obligation_file,
    generated_module_name,
    release_chain_values_from_obligations,
)
from pcs_core.validate import validate_file

LABTRUST = examples_dir() / "labtrust-release"


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
