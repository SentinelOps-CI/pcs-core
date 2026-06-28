"""Lean trust kernel bridge: proof obligations, lean-check CLI, formal_checks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pcs_core.lean_trust import (
    OBLIGATION_KIND_THEOREM,
    extract_proof_obligations_from_release,
    formal_checks_from_lean_result,
    run_lean_check,
)
from pcs_core.paths import examples_dir, repo_root
from pcs_core.release_chain_report import build_release_chain_validation_result
from pcs_core.validate import validate_file

LABTRUST = examples_dir() / "labtrust-release"
TOOL_USE = examples_dir() / "tool-use-release"
COMPUTATION = examples_dir() / "computation-release"


@pytest.mark.parametrize(
    "release_dir,expected_kinds",
    [
        (
            LABTRUST,
            {
                "CertificateMatchesRuntime",
                "VerificationAdmitsBundle",
                "SignedBundleAdmissible",
            },
        ),
        (
            TOOL_USE,
            {
                "ToolTraceHashMatchesCertificate",
                "CertificateMatchesRuntime",
                "VerificationAdmitsBundle",
                "SignedBundleAdmissible",
            },
        ),
        (
            COMPUTATION,
            {
                "ComputationWitnessHashAlignment",
                "VerificationAdmitsBundle",
                "SignedBundleAdmissible",
            },
        ),
    ],
)
def test_extract_proof_obligations_profiles(
    release_dir: Path,
    expected_kinds: set[str],
) -> None:
    doc = extract_proof_obligations_from_release(release_dir)
    kinds = {entry["kind"] for entry in doc["obligations"]}
    assert kinds == expected_kinds
    for entry in doc["obligations"]:
        assert entry["kind"] in OBLIGATION_KIND_THEOREM


def test_run_lean_check_passes_for_labtrust() -> None:
    obligations = extract_proof_obligations_from_release(LABTRUST)
    result = run_lean_check(obligations, require_lean_build=False)
    assert result["status"] == "ProofChecked"
    assert result["failure_reason"] == ""
    for item in result["obligation_results"]:
        assert item["status"] == "passed"


def test_formal_checks_from_lean_result() -> None:
    obligations = extract_proof_obligations_from_release(LABTRUST)
    lean_result = run_lean_check(obligations, require_lean_build=False)
    checks = formal_checks_from_lean_result(lean_result)
    assert checks
    assert any(c["check_id"].startswith("lean.") for c in checks)
    assert checks[-1]["check_id"] == "lean.kernel_build"


def test_cli_extract_and_lean_check(tmp_path: Path) -> None:
    out_obligations = tmp_path / "proof_obligation.v0.json"
    out_check = tmp_path / "lean_check_result.v0.json"
    root = repo_root()
    py = sys.executable
    extract = subprocess.run(
        [
            py,
            "-m",
            "pcs_core.cli",
            "extract-proof-obligations",
            "--release",
            str(LABTRUST / "release_manifest.v0.json"),
            "--out",
            str(out_obligations),
        ],
        cwd=root / "python",
        capture_output=True,
        text=True,
        check=False,
    )
    assert extract.returncode == 0, extract.stderr
    validate_file(out_obligations)

    lean_check = subprocess.run(
        [
            py,
            "-m",
            "pcs_core.cli",
            "pcs-envelope",
            "check",
            "--obligations",
            str(out_obligations),
            "--out",
            str(out_check),
            "--skip-lean-build",
        ],
        cwd=root / "python",
        capture_output=True,
        text=True,
        check=False,
    )
    assert lean_check.returncode == 0, lean_check.stderr
    validate_file(out_check)
    data = json.loads(out_check.read_text(encoding="utf-8"))
    assert data["status"] == "ProofChecked"


def test_release_chain_validation_includes_formal_checks_when_lean_result_present(
    tmp_path: Path,
) -> None:
    obligations = extract_proof_obligations_from_release(LABTRUST)
    lean_result = run_lean_check(obligations, require_lean_build=False)
    lean_path = tmp_path / "lean_check_result.v0.json"
    lean_path.write_text(json.dumps(lean_result, indent=2) + "\n", encoding="utf-8")

    for name in [
        "release_manifest.v0.json",
        "trace_certificate.json",
        "runtime_receipt.json",
        "verification_result.json",
        "signed_science_claim_bundle.json",
        "science_claim_bundle.certified.json",
    ]:
        src = LABTRUST / name
        if src.is_file():
            (tmp_path / name).write_bytes(src.read_bytes())

    result = build_release_chain_validation_result(tmp_path)
    assert "formal_checks" in result
    assert len(result["formal_checks"]) >= 1
