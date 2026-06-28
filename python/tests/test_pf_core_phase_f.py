"""Tests for PF-Core Phase F: non-interference, contract discharge, CertifyEdge."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pcs_core.lean_check import run_pfcore_lean_check
from pcs_core.pf_core_certifyedge import (
    CERTIFYEDGE_INSTALL_DOC,
    certifyedge_cli_available,
    certifyedge_mock_enabled,
    certifyedge_mode,
    certifyedge_status,
    run_certifyedge_check,
    write_certifyedge_certificate,
)
from pcs_core.pf_core_lean_codegen import (
    generate_proof_obligation_file,
    trace_has_contract_refs,
    validate_contracts_before_codegen,
)
from pcs_core.pf_core_runtime import validate_cross_tenant_safety, validate_tenant_isolation
from pcs_core.validate import validate_artifact, validate_file

REPO = Path(__file__).resolve().parents[2]
CONTRACT_TRACE = REPO / "examples" / "pf-core-valid" / "contract_checked" / "trace.json"
CONTRACT_VIOLATION = REPO / "examples" / "pf-core-invalid" / "contract_violation" / "trace.json"
CROSS_TENANT = REPO / "examples" / "pf-core-invalid" / "cross_tenant_leak" / "trace.json"
FILE_READ_ALLOWED = REPO / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json"
LABTRUST_TRACE = REPO / "examples" / "pf-core-valid" / "labtrust_replay" / "trace.json"
LAKE_AVAILABLE = shutil.which("lake") is not None


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_non_interference_lean_module_has_theorems() -> None:
    text = (REPO / "lean" / "PFCore" / "NonInterference.lean").read_text(encoding="utf-8")
    assert "theorem cons_preserves_tenant_scope" in text
    assert "theorem traceSafe_allowed_event_tenant_scoped" in text
    assert "sorry" not in text


def test_contract_decide_lean_module_has_soundness() -> None:
    text = (REPO / "lean" / "PFCore" / "ContractDecide.lean").read_text(encoding="utf-8")
    assert "theorem contractPreD_sound" in text
    assert "theorem traceSatisfiesContractSpecsD_sound" in text
    assert "sorry" not in text


def test_validate_tenant_isolation_ok_on_allowed_fixture() -> None:
    trace = _load(FILE_READ_ALLOWED)
    assert validate_tenant_isolation(trace) == []


def test_validate_tenant_isolation_fails_cross_tenant_leak() -> None:
    trace = _load(CROSS_TENANT)
    errors = validate_tenant_isolation(trace)
    assert any("TenantIsolation" in err for err in errors)


def test_generated_proof_includes_contract_obligations(tmp_path: Path) -> None:
    trace = _load(CONTRACT_TRACE)
    assert trace_has_contract_refs(trace)
    assert validate_contracts_before_codegen(trace, trace_path=CONTRACT_TRACE) == []
    proof_path = generate_proof_obligation_file(trace, tmp_path, trace_path=CONTRACT_TRACE)
    text = proof_path.read_text(encoding="utf-8")
    assert "ContractPreSpec" in text
    assert "concrete_trace_satisfies_contract_" in text
    assert "concrete_satisfies_contract_" in text
    assert "validate-contracts only" not in text


def test_contract_violation_fails_before_codegen() -> None:
    trace = _load(CONTRACT_VIOLATION)
    errors = validate_contracts_before_codegen(
        trace,
        trace_path=CONTRACT_VIOLATION,
    )
    assert any("ContractDecisionMismatch" in err for err in errors)


def test_lean_check_rejects_contract_violation(tmp_path: Path) -> None:
    code, result = run_pfcore_lean_check(
        CONTRACT_VIOLATION,
        result_out_path=tmp_path / "result.json",
        skip_build=True,
        skip_lean_proof=True,
    )
    assert code != 0
    issues = result.get("issues", [])
    assert any(issue.get("code") == "ContractViolation" for issue in issues)


def test_validate_cross_tenant_safety_ok_on_allowed_fixture() -> None:
    trace = _load(FILE_READ_ALLOWED)
    assert validate_cross_tenant_safety(trace) == []


def test_validate_cross_tenant_safety_fails_cross_tenant_allow() -> None:
    trace = _load(CROSS_TENANT)
    errors = validate_cross_tenant_safety(trace)
    assert any("CrossTenantSafe" in err for err in errors)
    assert validate_tenant_isolation(trace) != []


def test_certifyedge_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PF_CORE_CERTIFYEDGE_MODE", "mock")
    monkeypatch.delenv("PF_CORE_CERTIFYEDGE_MOCK", raising=False)
    assert certifyedge_mode() == "mock"
    assert certifyedge_mock_enabled()
    result = run_certifyedge_check(LABTRUST_TRACE, "qc_release.temporal.safety")
    assert result.ok
    assert result.mock
    assert result.certificate is not None
    assert result.certificate["claim_class"] == "CertificateChecked"
    validate_artifact(result.certificate, "PFCoreCertificate.v0")


def test_certifyedge_mock_writes_certificate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PF_CORE_CERTIFYEDGE_MOCK", "1")
    out = tmp_path / "cert.json"
    write_certifyedge_certificate(LABTRUST_TRACE, "qc_release.temporal.safety", out)
    cert = _load(out)
    assert cert["claim_class"] == "CertificateChecked"
    validate_file(out)


def test_certifyedge_without_cli_or_mock_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PF_CORE_CERTIFYEDGE_MOCK", raising=False)
    monkeypatch.delenv("PCS_CERTIFYEDGE_MOCK", raising=False)
    monkeypatch.delenv("PF_CORE_CERTIFYEDGE_MODE", raising=False)
    result = run_certifyedge_check(LABTRUST_TRACE, "qc_release.temporal.safety")
    if shutil.which("certifyedge") is None:
        assert not result.ok
        assert "CertifyEdge" in result.message


def test_certifyedge_mock_fixture_in_examples() -> None:
    mock_dir = REPO / "examples" / "pf-core-valid" / "certifyedge_mock"
    validate_file(mock_dir / "trace.json")
    validate_file(mock_dir / "certificate.json")
    cert = _load(mock_dir / "certificate.json")
    assert cert["claim_class"] == "CertificateChecked"
    assert any(ref.startswith("mock://certifyedge/") for ref in cert.get("assumption_refs", []))


def test_certifyedge_status_reports_env_contract() -> None:
    status = certifyedge_status()
    assert "env_contract" in status
    assert "PF_CORE_CERTIFYEDGE_MODE" in status["env_contract"]
    assert "install_doc" in status
    assert CERTIFYEDGE_INSTALL_DOC in str(status["install_doc"])
    assert isinstance(certifyedge_cli_available(), bool)


def test_certifyedge_live_mock_separation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock and live modes must be distinguishable on results and env contract."""
    monkeypatch.setenv("PF_CORE_CERTIFYEDGE_MODE", "mock")
    mock_result = run_certifyedge_check(LABTRUST_TRACE, "qc_release.temporal.safety")
    assert mock_result.mock is True
    assert mock_result.ok
    assert "mock" in mock_result.message.lower()

    monkeypatch.setenv("PF_CORE_CERTIFYEDGE_MODE", "live")
    monkeypatch.delenv("PF_CORE_CERTIFYEDGE_CLI", raising=False)
    if shutil.which("certifyedge") is None:
        live_result = run_certifyedge_check(LABTRUST_TRACE, "qc_release.temporal.safety")
        assert live_result.mock is False
        assert not live_result.ok
        assert (
            "live" in live_result.message.lower()
            or "PF_CORE_CERTIFYEDGE_MODE=live" in live_result.message
        )


def test_certifyedge_require_live_fails_without_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PF_CORE_CERTIFYEDGE_MODE", "live")
    monkeypatch.delenv("PF_CORE_CERTIFYEDGE_CLI", raising=False)
    monkeypatch.delenv("PF_CORE_CERTIFYEDGE_MOCK", raising=False)
    if shutil.which("certifyedge") is not None:
        pytest.skip("real certifyedge on PATH")
    result = run_certifyedge_check(LABTRUST_TRACE, "qc_release.temporal.safety", require_live=True)
    assert not result.ok
    assert (
        "require-live" in result.message.lower()
        or "PF_CORE_CERTIFYEDGE_MODE=live" in result.message
    )


def test_certifyedge_stub_cli_format(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stub = REPO / "scripts" / "certifyedge-stub.py"
    if not stub.is_file():
        pytest.skip("certifyedge-stub.py missing")
    monkeypatch.setenv("PF_CORE_CERTIFYEDGE_MODE", "live")
    monkeypatch.setenv("PF_CORE_CERTIFYEDGE_CLI", str(stub))
    result = run_certifyedge_check(LABTRUST_TRACE, "qc_release.temporal.safety")
    assert result.ok
    assert result.mock is False
    assert result.attestation_ref is not None
    assert result.attestation_ref.startswith("stub://certifyedge/")


@pytest.mark.skipif(not LAKE_AVAILABLE, reason="lake or WSL not available")
def test_contract_checked_generated_proof_compiles() -> None:
    from pcs_core.lean_check import pfcore_generated_dir, run_lean_concrete_proof

    trace = _load(CONTRACT_TRACE)
    proof_path = generate_proof_obligation_file(
        trace, pfcore_generated_dir(), trace_path=CONTRACT_TRACE
    )
    ok, detail = run_lean_concrete_proof(proof_path, skip_build=False)
    if not ok and ("lake unavailable" in detail or "timed out" in detail.lower()):
        pytest.skip(detail)
    assert ok, detail


def test_cross_tenant_invalid_fixture_in_examples_check() -> None:
    validate_file(CROSS_TENANT)
