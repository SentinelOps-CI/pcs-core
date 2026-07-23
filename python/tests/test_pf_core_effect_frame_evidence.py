"""PR4 effect-frame redesign: independent PFCoreEffectFrame.v0 + non-tautological proofs."""

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
    action_effects_in_declared_frame,
    effect_frame_allowed_kinds,
    effect_frame_source_digest,
    resolve_pf_core_evidence,
)
from pcs_core.pf_core_semantic_projection import build_semantic_projection
from pcs_core.validate import validate_artifact

REPO = Path(__file__).resolve().parents[2]
EFFECT_FRAME_FIXTURE = (
    REPO / "examples" / "pf-core-valid" / "certificate_mode_effectframecertificate"
)
EFFECT_FRAME_TRACE = EFFECT_FRAME_FIXTURE / "trace.json"
EFFECT_FRAME_JSON = EFFECT_FRAME_FIXTURE / "effect_frame.json"
ADVERSARIAL_FIXTURE = (
    REPO / "examples" / "pf-core-invalid" / "certificate_mode_effectframecertificate_extra_effect"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _prepare_case(
    tmp_path: Path,
    *,
    effect_frame_id: str | None,
    frame: dict[str, Any] | None = None,
    mutate_action_effects: list[dict[str, str]] | None = None,
) -> tuple[Path, dict[str, Any]]:
    work = tmp_path / "case"
    work.mkdir(parents=True, exist_ok=True)
    trace = dict(_load(EFFECT_FRAME_TRACE))
    if effect_frame_id is None:
        trace.pop("evidence_selection", None)
    else:
        trace["evidence_selection"] = {
            "policy": "explicit_ids",
            "policy_version": "v0",
            "effect_frame_id": effect_frame_id,
        }
    if mutate_action_effects is not None:
        for event in trace.get("events") or []:
            if isinstance(event, dict) and isinstance(event.get("action"), dict):
                event["action"]["effects"] = deepcopy(mutate_action_effects)
    from pcs_core.pf_core_runtime import compute_event_hash, compute_trace_hash

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
    trace_path = work / "trace.json"
    _write_json(trace_path, trace)
    body = dict(frame) if frame is not None else _load(EFFECT_FRAME_JSON)
    _write_json(work / "effect_frame.json", body)
    return trace_path, trace


def test_effect_frame_schema_validates() -> None:
    frame = _load(EFFECT_FRAME_JSON)
    validate_artifact(frame, "PFCoreEffectFrame.v0")
    assert frame["frame_scope_policy"] == "global"
    assert effect_frame_allowed_kinds(frame) == ["file.read"]


def test_effect_frame_requires_explicit_selection(tmp_path: Path) -> None:
    trace_path, trace = _prepare_case(tmp_path, effect_frame_id=None)
    with pytest.raises(EvidenceResolutionError, match="effect_frame_id"):
        resolve_pf_core_evidence(
            trace,
            trace_path=trace_path,
            certificate_mode="EffectFrameCertificate",
        )


def test_resolved_evidence_binds_independent_frame(tmp_path: Path) -> None:
    trace_path, trace = _prepare_case(
        tmp_path, effect_frame_id="frame-file-read-global-v0"
    )
    evidence = resolve_pf_core_evidence(
        trace,
        trace_path=trace_path,
        certificate_mode="EffectFrameCertificate",
    )
    assert evidence.effect_frame is not None
    assert evidence.effect_frame_path is not None
    assert evidence.effect_frame_path.name == "effect_frame.json"
    assert str(evidence.effect_frame.get("frame_id")) == "frame-file-read-global-v0"
    digest = effect_frame_source_digest(evidence)
    assert digest.startswith("sha256:")
    # Independence: frame kinds come from the artifact, not by copying action.effects field.
    action = (trace.get("events") or [{}])[0].get("action") or {}
    assert evidence.effect_frame is not action
    assert "effects" not in evidence.effect_frame


def test_codegen_uses_concrete_declared_frame_not_action_effects(tmp_path: Path) -> None:
    trace_path, trace = _prepare_case(
        tmp_path, effect_frame_id="frame-file-read-global-v0"
    )
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=trace_path,
        certificate_mode="EffectFrameCertificate",
    )
    text = generated.path.read_text(encoding="utf-8")
    assert "def concreteDeclaredFrame : List Effect :=" in text
    assert "actionEffectsInFrameD" in text
    assert "concreteDeclaredFrame = true" in text
    assert ".effects = true" not in text
    assert "import PFCore.EffectFrame" in text
    projection = generated.semantic_projection or {}
    assert "effect_frame" in projection
    assert projection["effect_frame"]["frame_id"] == "frame-file-read-global-v0"
    assert projection["effect_frame"]["frame_scope_policy"] == "global"


def test_projection_includes_effect_frame(tmp_path: Path) -> None:
    trace_path, trace = _prepare_case(
        tmp_path, effect_frame_id="frame-file-read-global-v0"
    )
    evidence = resolve_pf_core_evidence(
        trace,
        trace_path=trace_path,
        certificate_mode="EffectFrameCertificate",
    )
    projection = build_semantic_projection(
        trace,
        certificate_mode="EffectFrameCertificate",
        resolved_evidence=evidence,
    )
    validate_artifact(projection, "PFCoreSemanticProjection.v0")
    frame = projection["effect_frame"]
    assert frame["allowed_effect_kinds"] == ["file.read"]
    assert frame["source_policy_ref"].startswith("policy:")


def test_adversarial_extra_effect_omitted_from_frame_fails(tmp_path: Path) -> None:
    """Action with an extra effect not listed in the declared frame must fail."""
    frame = _load(EFFECT_FRAME_JSON)
    # Frame permits only file.read.
    assert frame["allowed_effect_kinds"] == ["file.read"]
    trace_path, trace = _prepare_case(
        tmp_path,
        effect_frame_id="frame-file-read-global-v0",
        frame=frame,
        mutate_action_effects=[
            {"effect_kind": "file.read"},
            {"effect_kind": "file.write"},
        ],
    )
    action = (trace.get("events") or [{}])[0].get("action") or {}
    assert not action_effects_in_declared_frame(action, frame)
    with pytest.raises(EvidenceResolutionError, match="undeclared effect"):
        resolve_pf_core_evidence(
            trace,
            trace_path=trace_path,
            certificate_mode="EffectFrameCertificate",
        )
    with pytest.raises(CertificateModeEvidenceMissing, match="undeclared effect|effect_frame"):
        generate_proof_obligation_file(
            trace,
            tmp_path / "out",
            trace_path=trace_path,
            certificate_mode="EffectFrameCertificate",
        )


def test_adversarial_fixture_directory_fails_resolution() -> None:
    trace_path = ADVERSARIAL_FIXTURE / "trace.json"
    trace = _load(trace_path)
    with pytest.raises(EvidenceResolutionError, match="undeclared effect"):
        resolve_pf_core_evidence(
            trace,
            trace_path=trace_path,
            certificate_mode="EffectFrameCertificate",
        )


def test_missing_selection_still_errors_in_codegen(tmp_path: Path) -> None:
    work = tmp_path / "case"
    work.mkdir()
    trace = dict(_load(EFFECT_FRAME_TRACE))
    trace.pop("evidence_selection", None)
    trace_path = work / "trace.json"
    _write_json(trace_path, trace)
    shutil.copy2(EFFECT_FRAME_JSON, work / "effect_frame.json")
    with pytest.raises(CertificateModeEvidenceMissing, match="effect_frame_id"):
        generate_proof_obligation_file(
            trace,
            tmp_path / "out",
            trace_path=trace_path,
            certificate_mode="EffectFrameCertificate",
        )


def test_public_issuance_still_disabled_without_allow_flag(tmp_path: Path) -> None:
    from pcs_core.lean_check import run_pfcore_lean_check

    case = tmp_path / "case"
    shutil.copytree(EFFECT_FRAME_FIXTURE, case)
    code, result = run_pfcore_lean_check(
        case / "trace.json",
        certificate_mode="EffectFrameCertificate",
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
    shutil.copytree(EFFECT_FRAME_FIXTURE, case)
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
            "EffectFrameCertificate",
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
    assert cert["certificate_mode"] == "EffectFrameCertificate"
    assert cert.get("lean_proof_checked") is True
    assert cert["effect_frame_id"] == "frame-file-read-global-v0"
    assert cert["effect_frame_path"]
    assert str(cert["effect_frame_digest"]).startswith("sha256:")
    # Certificate records the independent frame path/digest (not action.effects).
    assert "effect_frame.json" in cert["effect_frame_path"].replace("\\", "/")
