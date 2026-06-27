"""End-to-end LabTrust bridge demo tests (Phase E)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pcs_core.pf_core_certificate import attach_external_certificate_check
from pcs_core.pf_core_labtrust_adapter import normalize_labtrust_release
from pcs_core.pf_core_replay import replay_trace
from pcs_core.validate import validate_artifact, validate_file

REPO = Path(__file__).resolve().parents[2]
LABTRUST_TC = REPO / "examples" / "labtrust" / "trace_certificate.valid.json"
LABTRUST_SCB = REPO / "examples" / "labtrust" / "science_claim_bundle.certified.valid.json"
LABTRUST_TRACE = REPO / "examples" / "pf-core-valid" / "labtrust_replay" / "trace.json"
BRIDGE_SCRIPT = REPO / "scripts" / "pf-core-bridge-demo.sh"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_trace_certificate_validates() -> None:
    assert validate_file(LABTRUST_TC) == "TraceCertificate.v0"


def test_labtrust_adapter_produces_pfcore_trace() -> None:
    tc = _load(LABTRUST_TC)
    scb = _load(LABTRUST_SCB)
    receipt = scb["runtime_receipts"][0]
    trace = normalize_labtrust_release(tc, receipt)
    assert trace["artifact_type"] == "PFCoreTrace.v0"
    assert trace["events"][0]["contract_refs"]


def test_labtrust_replay_fixture_matches() -> None:
    result = replay_trace(LABTRUST_TRACE)
    assert result.match is True


def test_attach_certificate_check_bridge() -> None:
    trace = _load(LABTRUST_TRACE)
    cert = attach_external_certificate_check(
        trace,
        checker="certifyedge",
        checker_version="0.1.0",
        attestation_ref=str(LABTRUST_TC.relative_to(REPO)).replace("\\", "/"),
        assumption_refs=["as-labtrust-qc-v0.1"],
    )
    assert cert["claim_class"] == "CertificateChecked"
    assert cert["checker"] == "certifyedge"
    validate_artifact(cert, "PFCoreCertificate.v0")


def test_bridge_demo_script_runs() -> None:
    if sys.platform == "win32":
        pytest = __import__("pytest")
        pytest.skip("bridge shell script requires bash (use WSL or CI)")
    result = subprocess.run(
        ["bash", str(BRIDGE_SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_assumption_declared_fixture_uses_assumption_set_id() -> None:
    cert_path = REPO / "examples/pf-core-valid/assumption_declared/certificate.json"
    cert = _load(cert_path)
    assert "as-pfcore-demo-v0.1" in cert["assumption_refs"]
    validate_file(cert_path)
