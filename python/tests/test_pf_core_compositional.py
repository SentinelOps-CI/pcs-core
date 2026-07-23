"""Tests for PF-Core compositional trust Lean catalog and proof binding verification."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pcs_core.lean_catalog import PF_CORE_THEOREM_CATALOG
from pcs_core.lean_check import compute_proof_term_hash
from pcs_core.pf_core_claims import audit_lean_catalog
from pcs_core.pf_core_lean_codegen import (
    compute_lean_environment_hash,
    compute_pfcore_kernel_hash,
)
from pcs_core.pf_core_proof_binding import verify_proof_binding
from pcs_core.pf_core_runtime import compute_trace_hash
from pcs_core.validate import check_pf_core_invalid_fixtures

REPO = Path(__file__).resolve().parents[2]
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"
GENERATED_PROOF = REPO / "lean" / "PFCore" / "Generated" / "Trace_716cbed45d37ebe4.lean"

COMPOSITIONAL_THEOREMS = frozenset(
    {
        "safe_extension_preserves_trace_safe",
        "contract_invariant_preserved_by_safe_extension",
        "handoff_composition_does_not_expand_authority",
        "composed_contract_preserves_component_invariants",
        "compositional_safe_extension_yields_safe_extended_trace",
        "trace_prefix_safe_extension",
    }
)

ROLE_MAP_THEOREMS = frozenset(
    {
        "aligned_role_capability_granted",
        "aligned_principal_has_capability",
    }
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_compositional_theorems_in_catalog() -> None:
    missing = COMPOSITIONAL_THEOREMS - PF_CORE_THEOREM_CATALOG
    assert not missing, f"missing from PF_CORE_THEOREM_CATALOG: {sorted(missing)}"


def test_role_map_theorem_in_catalog() -> None:
    assert "aligned_role_capability_granted" in PF_CORE_THEOREM_CATALOG


def test_lean_catalog_includes_compositional_and_role_map() -> None:
    errors = audit_lean_catalog()
    compositional_errors = [
        err
        for err in errors
        if any(name in err for name in COMPOSITIONAL_THEOREMS | ROLE_MAP_THEOREMS)
    ]
    assert compositional_errors == [], compositional_errors


def test_compositional_lean_sources_exist() -> None:
    compositional = (REPO / "lean" / "PFCore" / "Compositional.lean").read_text(encoding="utf-8")
    assert "def CompositionalSafeExtension" in compositional
    assert "abbrev TracePrefixSafe" in compositional
    assert "theorem compositional_safe_extension_yields_safe_extended_trace" in compositional
    assert (REPO / "lean" / "PFCore" / "RoleMap.lean").is_file()


def test_invalid_fixture_harness_passes() -> None:
    check_pf_core_invalid_fixtures()


def test_verify_proof_binding_rejects_non_kernel_certificate(tmp_path: Path) -> None:
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-test",
        "trace_hash": "sha256:" + "a" * 64,
        "claim_class": "RuntimeChecked",
        "checker": "pcs-core",
        "checker_version": "0.1.0",
    }
    cert_path = tmp_path / "cert.json"
    cert_path.write_text(json.dumps(cert), encoding="utf-8")
    result = verify_proof_binding(cert_path, trace_path=VALID_TRACE)
    assert result.ok is False
    assert any(issue.code == "ClaimClassMismatch" for issue in result.issues)


def test_verify_proof_binding_detects_trace_hash_mismatch(tmp_path: Path) -> None:
    if not GENERATED_PROOF.is_file():
        pytest.skip("generated proof fixture missing")
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-test",
        "trace_hash": "sha256:" + "b" * 64,
        "claim_class": "LeanKernelChecked",
        "lean_proof_checked": True,
        "proof_term_ref": str(GENERATED_PROOF.relative_to(REPO)).replace("\\", "/"),
        "proof_term_hash": compute_proof_term_hash(GENERATED_PROOF),
        "lean_environment_hash": compute_lean_environment_hash(),
        "pfcore_kernel_hash": compute_pfcore_kernel_hash(),
    }
    cert_path = tmp_path / "cert.json"
    cert_path.write_text(json.dumps(cert), encoding="utf-8")
    result = verify_proof_binding(cert_path, trace_path=VALID_TRACE)
    assert result.ok is False
    assert any(issue.code == "TraceHashMismatch" for issue in result.issues)


def test_verify_proof_binding_ok_when_bound(tmp_path: Path) -> None:
    if not GENERATED_PROOF.is_file():
        pytest.skip("generated proof fixture missing")
    trace = _load(VALID_TRACE)
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-test",
        "trace_hash": trace.get("trace_hash") or compute_trace_hash(trace),
        "claim_class": "LeanKernelChecked",
        "lean_proof_checked": True,
        "proof_term_ref": str(GENERATED_PROOF.relative_to(REPO)).replace("\\", "/"),
        "proof_term_hash": compute_proof_term_hash(GENERATED_PROOF),
        "lean_environment_hash": compute_lean_environment_hash(),
        "pfcore_kernel_hash": compute_pfcore_kernel_hash(),
    }
    cert_path = tmp_path / "cert.json"
    cert_path.write_text(json.dumps(cert), encoding="utf-8")
    result = verify_proof_binding(cert_path, trace_path=VALID_TRACE)
    assert result.ok is True


def test_verify_proof_binding_cli(tmp_path: Path) -> None:
    if not GENERATED_PROOF.is_file():
        pytest.skip("generated proof fixture missing")
    trace = _load(VALID_TRACE)
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-cli",
        "trace_hash": trace.get("trace_hash") or compute_trace_hash(trace),
        "claim_class": "LeanKernelChecked",
        "lean_proof_checked": True,
        "proof_term_ref": str(GENERATED_PROOF.relative_to(REPO)).replace("\\", "/"),
        "proof_term_hash": compute_proof_term_hash(GENERATED_PROOF),
        "lean_environment_hash": compute_lean_environment_hash(),
        "pfcore_kernel_hash": compute_pfcore_kernel_hash(),
    }
    cert_path = tmp_path / "cert.json"
    cert_path.write_text(json.dumps(cert), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pcs_core.cli",
            "pf-core",
            "verify-proof-binding",
            "--certificate",
            str(cert_path),
            "--trace",
            str(VALID_TRACE),
        ],
        cwd=REPO / "python",
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
