"""Tests for PF-Core Stage 5 claim-class completeness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.pf_core_certificate import attach_external_certificate_check
from pcs_core.pf_core_labtrust_adapter import normalize_labtrust_release
from pcs_core.pf_core_replay import replay_trace, run_replay_trace
from pcs_core.registry_data import (
    deferred_registry_obligations,
    enforce_assumption_declared,
    registry_entries,
)
from pcs_core.validate import validate_file, validate_semantics

REPO = Path(__file__).resolve().parents[2]
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"
TOOL_USE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "tool_use_trace.json"
LABTRUST_TRACE = REPO / "examples" / "pf-core-valid" / "labtrust_replay" / "trace.json"
LABTRUST_TC = REPO / "examples" / "labtrust" / "trace_certificate.valid.json"
LABTRUST_SCB = REPO / "examples" / "labtrust" / "science_claim_bundle.certified.valid.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_valid_fixture_replay_passes() -> None:
    result = replay_trace(VALID_TRACE)
    assert result.match is True
    assert result.original_trace_hash == result.recomputed_trace_hash
    assert result.diffs == []


def test_tampered_hash_fails() -> None:
    trace = _load(VALID_TRACE)
    trace["trace_hash"] = "sha256:" + "f" * 64
    tampered = VALID_TRACE.parent / "tampered_trace.json"
    tampered.write_text(json.dumps(trace, indent=2), encoding="utf-8")
    try:
        result = replay_trace(tampered)
        assert result.match is False
        assert result.original_trace_hash != result.recomputed_trace_hash
        assert any(diff.path == "trace_hash" for diff in result.diffs)
    finally:
        tampered.unlink(missing_ok=True)


def test_tool_use_trace_compiled_replays_from_source() -> None:
    result = replay_trace(VALID_TRACE, TOOL_USE)
    assert result.match is True
    assert result.diffs == []


def test_run_replay_trace_emits_certificate(tmp_path: Path) -> None:
    out = tmp_path / "PFCoreCertificate.v0.json"
    result_out = tmp_path / "LeanCheckResult.v0.json"
    code, result = run_replay_trace(
        VALID_TRACE,
        out_path=out,
        result_out_path=result_out,
    )
    assert code == 0
    assert result["claim_class"] == "ReplayValidated"
    assert result["replay_match"] is True
    cert = json.loads(out.read_text(encoding="utf-8"))
    assert cert["claim_class"] == "ReplayValidated"
    assert cert["replay_match"] is True
    validate_file(out)
    validate_file(result_out)


def test_deferred_registry_obligations_present() -> None:
    deferred = deferred_registry_obligations("PFCoreCertificate.v0")
    check_ids = {item["check_id"] for item in deferred}
    assert "lean_kernel_proof" in check_ids
    assert "lean_library_build" in check_ids


def test_certificate_with_deferred_check_and_no_assumption_refs_fails() -> None:
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-test",
        "trace_hash": "sha256:" + "0" * 64,
        "contract_hash": "sha256:" + "0" * 64,
        "policy_hash": "sha256:" + "0" * 64,
        "claim_class": "AssumptionDeclared",
        "checker": "pcs-core",
        "checker_version": "0.1.0",
        "assumption_refs": [],
        "event_count": 0,
        "source_repo": "https://github.com/example/pcs-core",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    issues = enforce_assumption_declared(cert, registry_entries()["PFCoreCertificate.v0"])
    assert issues
    semantic = validate_semantics(cert, "PFCoreCertificate.v0")
    assert any("assumption_refs" in err for err in semantic)


def test_certificate_with_deferred_check_and_refs_passes_as_assumption_declared() -> None:
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-test",
        "trace_hash": "sha256:" + "0" * 64,
        "contract_hash": "sha256:" + "0" * 64,
        "policy_hash": "sha256:" + "0" * 64,
        "claim_class": "AssumptionDeclared",
        "checker": "pcs-core",
        "checker_version": "0.1.0",
        "assumption_refs": ["docs/pf-core/assumptions.md", "as-labtrust-qc-v0.1"],
        "event_count": 0,
        "source_repo": "https://github.com/example/pcs-core",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    issues = enforce_assumption_declared(cert, registry_entries()["PFCoreCertificate.v0"])
    assert issues == []


def test_lean_kernel_checked_forbidden_when_deferred_skipped() -> None:
    cert = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "pfcore-cert-test",
        "trace_hash": "sha256:" + "0" * 64,
        "contract_hash": "sha256:" + "0" * 64,
        "policy_hash": "sha256:" + "0" * 64,
        "claim_class": "LeanKernelChecked",
        "checker": "pcs-core",
        "checker_version": "0.1.0",
        "proof_term_ref": "lean/PFCore/Generated/proof.lean",
        "proof_ref": "lean/PFCore/Generated/proof.lean",
        "lean_proof_checked": True,
        "lean_build_status": {"ok": False, "target": "PFCore", "detail": "skipped"},
        "assumption_refs": ["docs/pf-core/assumptions.md"],
        "event_count": 1,
        "source_repo": "https://github.com/example/pcs-core",
        "source_commit": "abc1234567890abc1234567890abc1234567890",
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    issues = enforce_assumption_declared(cert, registry_entries()["PFCoreCertificate.v0"])
    assert any("LeanKernelChecked" in issue for issue in issues)


def test_attach_certificate_check_emits_certificate_checked(tmp_path: Path) -> None:
    trace = _load(VALID_TRACE)
    cert = attach_external_certificate_check(
        trace,
        checker="certifyedge",
        checker_version="0.1.0",
        attestation_ref="examples/labtrust/trace_certificate.valid.json",
    )
    out = tmp_path / "cert.json"
    out.write_text(json.dumps(cert, indent=2), encoding="utf-8")
    assert cert["claim_class"] == "CertificateChecked"
    validate_file(out)


def test_labtrust_adapter_trace_validates() -> None:
    validate_file(LABTRUST_TRACE)


def test_labtrust_adapter_matches_fixture() -> None:
    tc = _load(LABTRUST_TC)
    scb = _load(LABTRUST_SCB)
    receipt = scb["runtime_receipts"][0]
    adapted = normalize_labtrust_release(tc, receipt)
    expected = _load(LABTRUST_TRACE)
    assert adapted["trace_hash"] == expected["trace_hash"]
    assert adapted["contract_hash"] == expected["contract_hash"]
    assert adapted["policy_hash"] == expected["policy_hash"]


def test_labtrust_replay_passes() -> None:
    result = replay_trace(LABTRUST_TRACE)
    assert result.match is True
