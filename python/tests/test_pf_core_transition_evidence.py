"""PR5 transition-certificate redesign: stepState witnesses + cross-tenant reject."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from pcs_core.pf_core_lean_codegen import (
    CertificateModeEvidenceMissing,
    generate_proof_obligation_file,
)
from pcs_core.pf_core_resolved_evidence import (
    EvidenceResolutionError,
    resolve_pf_core_evidence,
    simulate_frame_preserved_transitions,
    step_state,
    transition_chain_digest,
)
from pcs_core.pf_core_runtime import compute_event_hash, compute_trace_hash
from pcs_core.pf_core_semantic_projection import build_semantic_projection
from pcs_core.validate import validate_artifact

REPO = Path(__file__).resolve().parents[2]
VALID_FIXTURE = (
    REPO / "examples" / "pf-core-valid" / "certificate_mode_framepreservedcertificate"
)
VALID_TRACE = VALID_FIXTURE / "trace.json"
CROSS_TENANT_NOOP = (
    REPO
    / "examples"
    / "pf-core-invalid"
    / "certificate_mode_framepreservedcertificate_cross_tenant_noop"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _finalize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    events = trace.get("events") or []
    prev = "sha256:" + "0" * 64
    for event in events:
        if not isinstance(event, dict):
            continue
        event["previous_event_hash"] = prev
        event.pop("event_hash", None)
        event.pop("signature_or_digest", None)
        digest = compute_event_hash(event)
        event["event_hash"] = digest
        event["signature_or_digest"] = digest
        prev = digest
    trace.pop("trace_hash", None)
    trace.pop("signature_or_digest", None)
    trace["trace_hash"] = compute_trace_hash(trace)
    trace["signature_or_digest"] = trace["trace_hash"]
    return trace


def test_resolved_evidence_binds_transition_states() -> None:
    trace = _load(VALID_TRACE)
    evidence = resolve_pf_core_evidence(
        trace,
        trace_path=VALID_TRACE,
        certificate_mode="FramePreservedCertificate",
    )
    assert evidence.initial_state is not None
    assert len(evidence.transition_states) == 2
    assert evidence.initial_state["tenant"] == "tenant-a"
    assert evidence.transition_states[0]["resource_frame"]
    # Deny is identity relative to the post-allow state.
    assert evidence.transition_states[1] == evidence.transition_states[0]
    digest = transition_chain_digest(evidence)
    assert digest.startswith("sha256:")


def test_codegen_emits_step_state_witnesses_not_apply_event(tmp_path: Path) -> None:
    generated = generate_proof_obligation_file(
        _load(VALID_TRACE),
        tmp_path / "out",
        trace_path=VALID_TRACE,
        certificate_mode="FramePreservedCertificate",
    )
    text = generated.path.read_text(encoding="utf-8")
    assert "import PFCore.Transition" in text
    assert "stepState" in text
    assert "step_state_applies_" in text
    assert "resource_frame_update_" in text
    assert "active_principal_update_" in text
    assert "tenant_update_" in text
    assert "capability_frame_update_" in text
    assert "deny_identity_" in text
    assert "frame_valid_after_" in text
    assert "expandResourceFrame" in text
    # No applyEvent expressions in obligations (docstring may mention the ban).
    assert "frameValidD (applyEvent" not in text
    assert ":= applyEvent" not in text
    assert "frame_preserved_steps" in text
    projection = generated.semantic_projection or {}
    assert "initial_state" in projection
    assert "transition_states" in projection
    assert len(projection["transition_states"]) == 2


def test_projection_includes_operational_states() -> None:
    evidence = resolve_pf_core_evidence(
        _load(VALID_TRACE),
        trace_path=VALID_TRACE,
        certificate_mode="FramePreservedCertificate",
    )
    projection = build_semantic_projection(
        _load(VALID_TRACE),
        certificate_mode="FramePreservedCertificate",
        resolved_evidence=evidence,
    )
    validate_artifact(projection, "PFCoreSemanticProjection.v0")
    assert projection["initial_state"]["tenant"] == "tenant-a"
    assert len(projection["transition_states"]) == 2


def test_sequential_cross_tenant_allow_rejected_as_noop() -> None:
    """Legacy applyEvent would no-op the second allow; remediated mode must reject."""
    trace_path = CROSS_TENANT_NOOP / "trace.json"
    trace = _load(trace_path)
    events = [event for event in (trace.get("events") or []) if isinstance(event, dict)]
    assert len(events) == 2
    assert events[0]["principal"]["tenant"] != events[1]["principal"]["tenant"]

    initial, posts = simulate_frame_preserved_transitions(events[:1])
    # After first allow, second allow returns none (the silent applyEvent fallback case).
    assert step_state(posts[0], events[1]) is None

    with pytest.raises(EvidenceResolutionError, match="stepState failed|no-op"):
        resolve_pf_core_evidence(
            trace,
            trace_path=trace_path,
            certificate_mode="FramePreservedCertificate",
        )
    with pytest.raises(CertificateModeEvidenceMissing, match="stepState failed|no-op"):
        generate_proof_obligation_file(
            trace,
            Path(trace_path).parent / "_out_should_fail",
            trace_path=trace_path,
            certificate_mode="FramePreservedCertificate",
        )


def test_cross_tenant_fixture_directory_fails_resolution() -> None:
    trace_path = CROSS_TENANT_NOOP / "trace.json"
    with pytest.raises(EvidenceResolutionError, match="stepState failed"):
        resolve_pf_core_evidence(
            _load(trace_path),
            trace_path=trace_path,
            certificate_mode="FramePreservedCertificate",
        )


def test_public_issuance_still_disabled_without_allow_flag(tmp_path: Path) -> None:
    from pcs_core.lean_check import run_pfcore_lean_check

    case = tmp_path / "case"
    shutil.copytree(VALID_FIXTURE, case)
    code, result = run_pfcore_lean_check(
        case / "trace.json",
        certificate_mode="FramePreservedCertificate",
        skip_build=True,
        allow_non_public_modes=False,
    )
    assert code != 0
    codes = [issue.get("code") for issue in result.get("issues", [])]
    assert "CertificateModeIssuanceDenied" in codes


def test_cli_issuance_with_allow_non_public_modes(tmp_path: Path) -> None:
    if shutil.which("lake") is None:
        pytest.skip("lake not available for full Lean execution path")
    case = tmp_path / "case"
    shutil.copytree(VALID_FIXTURE, case)
    out_cert = tmp_path / "PFCoreCertificate.v0.json"
    result_out = tmp_path / "LeanCheckResult.v0.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pcs_core.cli",
            "pf-core",
            "lean-check",
            "--trace",
            str(case / "trace.json"),
            "--out",
            str(out_cert),
            "--result-out",
            str(result_out),
            "--certificate-mode",
            "FramePreservedCertificate",
            "--allow-non-public-modes",
        ],
        cwd=REPO / "python",
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert out_cert.is_file()
    cert = _load(out_cert)
    validate_artifact(cert, "PFCoreCertificate.v0")
    assert cert["certificate_mode"] == "FramePreservedCertificate"
    assert cert.get("lean_proof_checked") is True
    assert str(cert.get("transition_chain_digest") or "").startswith("sha256:")
    assert cert.get("transition_event_count") == 2


def test_same_tenant_sequential_allows_succeed(tmp_path: Path) -> None:
    work = tmp_path / "case"
    work.mkdir()
    trace = deepcopy(_load(VALID_TRACE))
    first = trace["events"][0]
    second = deepcopy(first)
    second["event_id"] = "ev-allow-2"
    second["sequence"] = 1
    second["decision"] = "allow"
    second["action"] = deepcopy(first["action"])
    second["action"]["action_id"] = "act-allow-2"
    second["action"]["reads"] = [
        {
            "resource_id": "res-2",
            "uri": "/data/report-2.txt",
            "tenant": "tenant-a",
        }
    ]
    # Drop the deny from the fixture; two same-tenant allows.
    trace["events"] = [first, second]
    trace = _finalize_trace(trace)
    trace_path = work / "trace.json"
    _write_json(trace_path, trace)
    evidence = resolve_pf_core_evidence(
        trace,
        trace_path=trace_path,
        certificate_mode="FramePreservedCertificate",
    )
    assert len(evidence.transition_states) == 2
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=trace_path,
        certificate_mode="FramePreservedCertificate",
    )
    text = generated.path.read_text(encoding="utf-8")
    assert text.count("step_state_applies_") >= 2
    assert "deny_identity_" not in text
    assert "frameValidD (applyEvent" not in text
    assert ":= applyEvent" not in text
