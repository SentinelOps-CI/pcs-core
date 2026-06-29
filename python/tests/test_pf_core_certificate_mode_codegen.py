"""Tests for substantive certificate-mode Lean codegen (no trivial aggregates)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pcs_core.pf_core_lean_codegen import (
    CERTIFICATE_MODES,
    generate_proof_obligation_file,
    resolve_certificate_mode,
)

REPO = Path(__file__).resolve().parents[2]
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"
FILE_READ = REPO / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json"
HANDOFF_FIXTURE = REPO / "examples" / "pf-core-valid" / "handoff_subset_authority" / "handoff.json"
CONTRACT_TRACE = REPO / "examples" / "pf-core-valid" / "contract_checked" / "trace.json"

TRIVIAL_RE = re.compile(r":\s*True\s*:=\s*trivial")


def _load(path: Path) -> dict:
    return __import__("json").loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "mode,trace_path",
    [
        ("FramePreservedCertificate", FILE_READ),
        ("EffectFrameCertificate", FILE_READ),
        ("HandoffSafeCertificate", VALID_TRACE),
        ("CompositionalExtensionCertificate", FILE_READ),
        ("ContractCheckedCertificate", CONTRACT_TRACE),
        ("TraceSafeRCertificate", VALID_TRACE),
    ],
)
def test_certificate_mode_codegen_has_no_trivial_aggregates(
    tmp_path: Path, mode: str, trace_path: Path
) -> None:
    trace = _load(trace_path)
    work = tmp_path / mode
    work.mkdir(parents=True, exist_ok=True)
    trace_file = work / "pfcore_trace.json"
    trace_file.write_text(json.dumps(trace), encoding="utf-8")
    if mode == "HandoffSafeCertificate":
        handoff = _load(HANDOFF_FIXTURE)
        (work / "handoff.json").write_text(json.dumps(handoff), encoding="utf-8")
    proof_path = generate_proof_obligation_file(
        trace,
        work / "out",
        trace_path=trace_file,
        certificate_mode=mode,
    )
    text = proof_path.read_text(encoding="utf-8")
    assert TRIVIAL_RE.search(text) is None, f"{mode} still emits trivial aggregate"
    assert f"Certificate mode: `{mode}`" in text


def test_tool_use_default_certificate_mode_is_trace_safe_r() -> None:
    trace = _load(VALID_TRACE)
    assert resolve_certificate_mode(trace, trace_path=VALID_TRACE) == "TraceSafeRCertificate"
    assert trace.get("required_certificate_mode") == "TraceSafeRCertificate"


def test_tool_use_certificate_mode_from_workflow_profile_without_trace_field(
    tmp_path: Path,
) -> None:
    trace = dict(_load(FILE_READ))
    trace["workflow_id"] = "agent_tool_use.safety_v0"
    trace.pop("required_certificate_mode", None)
    trace_file = tmp_path / "pfcore_trace.json"
    trace_file.write_text(json.dumps(trace), encoding="utf-8")
    assert resolve_certificate_mode(trace, trace_path=trace_file) == "TraceSafeRCertificate"


def test_release_grade_rejects_trace_safe_certificate_on_tool_use() -> None:
    from pcs_core.lean_check import run_pfcore_lean_check

    work = REPO / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json"
    code, result = run_pfcore_lean_check(
        work,
        release_grade=True,
        certificate_mode="TraceSafeCertificate",
    )
    assert code != 0
    codes = [issue.get("code") for issue in result.get("issues", [])]
    assert "CertificateModePolicyViolation" in codes


def test_release_grade_skips_sibling_tool_use_heuristic(tmp_path: Path) -> None:
    trace = dict(_load(FILE_READ))
    trace.pop("workflow_id", None)
    trace.pop("required_certificate_mode", None)
    trace_file = tmp_path / "pfcore_trace.json"
    trace_file.write_text(json.dumps(trace), encoding="utf-8")
    (tmp_path / "tool_use_trace.json").write_text("{}", encoding="utf-8")
    assert (
        resolve_certificate_mode(trace, trace_path=trace_file, release_grade=False)
        == "TraceSafeRCertificate"
    )
    assert (
        resolve_certificate_mode(trace, trace_path=trace_file, release_grade=True)
        == "TraceSafeCertificate"
    )


def test_release_grade_tool_use_without_policy_fails_lean_check(tmp_path: Path) -> None:
    from pcs_core.lean_check import run_pfcore_lean_check
    from pcs_core.pf_core_runtime import compute_trace_hash

    trace = dict(_load(FILE_READ))
    trace.pop("required_certificate_mode", None)
    trace["workflow_id"] = "custom.agent.v0"
    trace.pop("trace_hash", None)
    trace.pop("signature_or_digest", None)
    trace["trace_hash"] = compute_trace_hash(trace)
    trace["signature_or_digest"] = trace["trace_hash"]
    trace_file = tmp_path / "pfcore_trace.json"
    trace_file.write_text(json.dumps(trace), encoding="utf-8")
    tool_use_src = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "tool_use_trace.json"
    (tmp_path / "tool_use_trace.json").write_text(
        tool_use_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    code, result = run_pfcore_lean_check(trace_file, release_grade=True, skip_build=True)
    assert code != 0
    codes = [issue.get("code") for issue in result.get("issues", [])]
    assert "CertificateModePolicyViolation" in codes


def test_trace_safe_r_certificate_requires_resource_scope_theorems(tmp_path: Path) -> None:
    trace = _load(VALID_TRACE)
    proof_path = generate_proof_obligation_file(
        trace,
        tmp_path,
        trace_path=VALID_TRACE,
        certificate_mode="TraceSafeRCertificate",
    )
    text = proof_path.read_text(encoding="utf-8")
    assert "theorem concrete_trace_safe_r " in text
    assert "theorem concrete_trace_safe_r_prop" in text
    assert "theorem concrete_action_resource_scope_" in text
    assert "And.intro" in text or "frame_preserved_steps" not in text


def test_all_certificate_modes_registered() -> None:
    assert "TraceSafeRCertificate" in CERTIFICATE_MODES
