"""PR2 handoff evidence fidelity + PFCoreResolvedEvidence tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from pcs_core.hash import canonical_hash
from pcs_core.obligation_extraction_errors import ObligationExtractionError
from pcs_core.pf_core_bundle import bundle_release, validate_bundle
from pcs_core.pf_core_lean_codegen import (
    CertificateModeEvidenceMissing,
    generate_proof_obligation_file,
    handoff_to_lean,
)
from pcs_core.pf_core_resolved_evidence import (
    EvidenceResolutionError,
    assert_handoff_capability_fidelity,
    delegated_capability_ids,
    resolve_pf_core_evidence,
)
from pcs_core.pf_core_semantic_projection import (
    build_semantic_projection,
    extract_lean_delegated_capability_sequences,
    projection_handoffs,
)
from pcs_core.validate import validate_artifact

REPO = Path(__file__).resolve().parents[2]
FILE_READ = REPO / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json"
HANDOFF_FIXTURE = REPO / "examples" / "pf-core-valid" / "handoff_subset_authority" / "handoff.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _base_principal(*, tenant: str = "tenant-a", capabilities: list[str] | None = None) -> dict:
    return {
        "principal_id": "agent-1",
        "principal_kind": "agent",
        "tenant": tenant,
        "roles": ["agent"],
        "capabilities": capabilities
        or ["cap:file-read", "cap:email-send", "cap:handoff", "cap:mcp-invoke"],
    }


def _to_principal(*, tenant: str = "tenant-a") -> dict:
    return {
        "principal_id": "agent-2",
        "principal_kind": "agent",
        "tenant": tenant,
        "roles": ["handoff_delegate"],
        "capabilities": [],
    }


def _capability(cap_id: str) -> dict[str, str]:
    from pcs_core.pf_core_catalog import CAPABILITY_CATALOG

    entry = CAPABILITY_CATALOG[cap_id]
    return {
        "capability_id": entry["capability_id"],
        "effect_kind": entry["effect_kind"],
        "resource_pattern": entry["resource_pattern"],
    }


def _make_handoff(
    *,
    handoff_id: str,
    delegated: list[str],
    from_caps: list[str] | None = None,
    from_tenant: str = "tenant-a",
    to_tenant: str = "tenant-a",
) -> dict[str, Any]:
    body = {
        "schema_version": "v0",
        "artifact_type": "PFCoreHandoff.v0",
        "handoff_id": handoff_id,
        "from_principal": _base_principal(tenant=from_tenant, capabilities=from_caps),
        "to_principal": _to_principal(tenant=to_tenant),
        "delegated_capabilities": [_capability(cap_id) for cap_id in delegated],
        "reason": f"test handoff {handoff_id}",
        "evidence_refs": ["evidence/handoff.v0"],
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    body["signature_or_digest"] = canonical_hash(body)
    return body


def _prepare_case(
    tmp_path: Path,
    *,
    handoffs: list[dict[str, Any]],
    selected_ids: list[str],
    mode: str = "HandoffSafeCertificate",
) -> tuple[Path, dict[str, Any]]:
    work = tmp_path / "case"
    work.mkdir(parents=True, exist_ok=True)
    trace = dict(_load(FILE_READ))
    trace["required_certificate_mode"] = mode
    trace["evidence_selection"] = {
        "policy": "explicit_ids",
        "policy_version": "v0",
        "handoff_ids": selected_ids,
    }
    # Rebind digests after mutation.
    from pcs_core.pf_core_runtime import compute_trace_hash

    trace.pop("trace_hash", None)
    trace.pop("signature_or_digest", None)
    trace["trace_hash"] = compute_trace_hash(trace)
    trace["signature_or_digest"] = trace["trace_hash"]
    trace_path = work / "trace.json"
    _write_json(trace_path, trace)
    for handoff in handoffs:
        _write_json(work / f"{handoff['handoff_id']}.json", handoff)
    return trace_path, trace


def _assert_fidelity(source: list[dict], projection: dict, lean_source: str) -> None:
    projected = projection_handoffs(projection)
    lean_ids = extract_lean_delegated_capability_sequences(lean_source)
    assert_handoff_capability_fidelity(
        source_handoffs=source,
        projected_handoffs=projected,
        lean_capability_sequences=lean_ids,
    )


def test_one_capability_safe_delegation(tmp_path: Path) -> None:
    handoff = _make_handoff(handoff_id="handoff-one", delegated=["cap:handoff"])
    trace_path, trace = _prepare_case(
        tmp_path, handoffs=[handoff], selected_ids=["handoff-one"]
    )
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=trace_path,
        certificate_mode="HandoffSafeCertificate",
    )
    assert generated.semantic_projection is not None
    text = generated.path.read_text(encoding="utf-8")
    assert 'delegatedCapabilities := ["cap:handoff"]' in text
    _assert_fidelity([handoff], dict(generated.semantic_projection), text)
    validate_artifact(dict(generated.semantic_projection), "PFCoreSemanticProjection.v0")


def test_multi_capability_safe_delegation(tmp_path: Path) -> None:
    caps = ["cap:file-read", "cap:handoff", "cap:mcp-invoke"]
    handoff = _make_handoff(
        handoff_id="handoff-multi",
        delegated=caps,
        from_caps=["cap:file-read", "cap:email-send", "cap:handoff", "cap:mcp-invoke"],
    )
    trace_path, trace = _prepare_case(
        tmp_path, handoffs=[handoff], selected_ids=["handoff-multi"]
    )
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=trace_path,
        certificate_mode="HandoffSafeCertificate",
    )
    text = generated.path.read_text(encoding="utf-8")
    assert delegated_capability_ids(projection_handoffs(generated.semantic_projection)[0]) == caps
    _assert_fidelity([handoff], dict(generated.semantic_projection), text)


def _handoff_safe_python(handoff: Mapping[str, Any]) -> bool:
    """Mirror Lean ``handoffSafeD``: delegated ⊆ from.capabilities and same tenant."""
    from_p = handoff.get("from_principal")
    to_p = handoff.get("to_principal")
    if not isinstance(from_p, Mapping) or not isinstance(to_p, Mapping):
        return False
    allowed = {str(cap) for cap in (from_p.get("capabilities") or []) if str(cap)}
    if not all(cap_id in allowed for cap_id in delegated_capability_ids(handoff)):
        return False
    return str(from_p.get("tenant") or "") == str(to_p.get("tenant") or "")


def test_capability_absent_from_source_principal(tmp_path: Path) -> None:
    handoff = _make_handoff(
        handoff_id="handoff-absent",
        delegated=["cap:network"],
        from_caps=["cap:handoff"],
    )
    assert _handoff_safe_python(handoff) is False
    trace_path, trace = _prepare_case(
        tmp_path, handoffs=[handoff], selected_ids=["handoff-absent"]
    )
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=trace_path,
        certificate_mode="HandoffSafeCertificate",
    )
    text = generated.path.read_text(encoding="utf-8")
    assert "handoffSafeD" in text
    assert 'delegatedCapabilities := ["cap:network"]' in text
    # Lean decide cannot discharge handoffSafeD when the capability is absent.
    if shutil.which("lake") is not None:
        from pcs_core.lean_check import run_lean_concrete_proof

        ok, detail = run_lean_concrete_proof(generated.path, skip_build=False)
        if "lake unavailable" in detail or "timed out" in detail.lower():
            pytest.skip(detail)
        assert ok is False


def test_cross_tenant_delegation(tmp_path: Path) -> None:
    handoff = _make_handoff(
        handoff_id="handoff-xtenant",
        delegated=["cap:handoff"],
        from_tenant="tenant-a",
        to_tenant="tenant-b",
    )
    assert _handoff_safe_python(handoff) is False
    trace_path, trace = _prepare_case(
        tmp_path, handoffs=[handoff], selected_ids=["handoff-xtenant"]
    )
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=trace_path,
        certificate_mode="HandoffSafeCertificate",
    )
    assert "handoffSafeD" in generated.path.read_text(encoding="utf-8")
    if shutil.which("lake") is not None:
        from pcs_core.lean_check import run_lean_concrete_proof

        ok, detail = run_lean_concrete_proof(generated.path, skip_build=False)
        if "lake unavailable" in detail or "timed out" in detail.lower():
            pytest.skip(detail)
        assert ok is False


def test_empty_projected_delegation(tmp_path: Path) -> None:
    handoff = _make_handoff(handoff_id="handoff-empty", delegated=["cap:handoff"])
    handoff["delegated_capabilities"] = []
    with pytest.raises(ObligationExtractionError, match="non-empty"):
        build_semantic_projection(
            {"trace_id": "t", "events": []},
            certificate_mode="HandoffSafeCertificate",
            handoffs=[handoff],
        )


def test_reordered_delegation_preserves_sequence(tmp_path: Path) -> None:
    order_a = ["cap:file-read", "cap:handoff"]
    order_b = ["cap:handoff", "cap:file-read"]
    handoff = _make_handoff(
        handoff_id="handoff-order",
        delegated=order_a,
        from_caps=["cap:file-read", "cap:handoff"],
    )
    trace_path, trace = _prepare_case(
        tmp_path, handoffs=[handoff], selected_ids=["handoff-order"]
    )
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=trace_path,
        certificate_mode="HandoffSafeCertificate",
    )
    text = generated.path.read_text(encoding="utf-8")
    lean_seqs = extract_lean_delegated_capability_sequences(text)
    assert lean_seqs == [order_a]
    assert lean_seqs != [order_b]
    # Explicit Lean emitter order check.
    lean_fragment = handoff_to_lean(
        projection_handoffs(generated.semantic_projection)[0], name="handoffOrder"
    )
    assert 'delegatedCapabilities := ["cap:file-read", "cap:handoff"]' in lean_fragment


def test_unrelated_sibling_handoff_not_selected(tmp_path: Path) -> None:
    selected = _make_handoff(handoff_id="handoff-selected", delegated=["cap:handoff"])
    sibling = _make_handoff(
        handoff_id="handoff-unrelated",
        delegated=["cap:file-read"],
        from_caps=["cap:file-read", "cap:handoff"],
    )
    trace_path, trace = _prepare_case(
        tmp_path,
        handoffs=[selected, sibling],
        selected_ids=["handoff-selected"],
    )
    evidence = resolve_pf_core_evidence(
        trace,
        trace_path=trace_path,
        certificate_mode="HandoffSafeCertificate",
    )
    assert evidence.selected_handoff_ids == ("handoff-selected",)
    assert [item.handoff_id for item in evidence.handoffs] == ["handoff-selected"]
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=trace_path,
        certificate_mode="HandoffSafeCertificate",
        resolved_evidence=evidence,
    )
    projected = projection_handoffs(generated.semantic_projection)
    assert len(projected) == 1
    assert projected[0]["handoff_id"] == "handoff-selected"
    assert "handoff-unrelated" not in generated.path.read_text(encoding="utf-8")


def test_projection_mutation_after_proof_generation(tmp_path: Path) -> None:
    handoff = _make_handoff(handoff_id="handoff-mut-proj", delegated=["cap:handoff"])
    trace_path, trace = _prepare_case(
        tmp_path, handoffs=[handoff], selected_ids=["handoff-mut-proj"]
    )
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=trace_path,
        certificate_mode="HandoffSafeCertificate",
    )
    projection_path = tmp_path / "out" / "PFCoreSemanticProjection.v0.json"
    assert projection_path.is_file()
    original_hash = generated.semantic_projection_hash
    mutated = dict(generated.semantic_projection)
    mutated["handoffs"][0]["delegated_capabilities"] = [
        _capability("cap:file-read"),
        _capability("cap:handoff"),
    ]
    mutated.pop("projection_hash", None)
    mutated["projection_hash"] = canonical_hash(mutated)
    _write_json(projection_path, mutated)
    reloaded = _load(projection_path)
    assert reloaded["projection_hash"] != original_hash
    lean_ids = extract_lean_delegated_capability_sequences(
        generated.path.read_text(encoding="utf-8")
    )
    with pytest.raises(EvidenceResolutionError, match="fidelity"):
        assert_handoff_capability_fidelity(
            source_handoffs=[handoff],
            projected_handoffs=projection_handoffs(reloaded),
            lean_capability_sequences=lean_ids,
        )


def test_source_handoff_mutation_after_projection(tmp_path: Path) -> None:
    handoff = _make_handoff(
        handoff_id="handoff-mut-src",
        delegated=["cap:handoff"],
        from_caps=["cap:file-read", "cap:handoff"],
    )
    trace_path, trace = _prepare_case(
        tmp_path, handoffs=[handoff], selected_ids=["handoff-mut-src"]
    )
    evidence = resolve_pf_core_evidence(
        trace,
        trace_path=trace_path,
        certificate_mode="HandoffSafeCertificate",
    )
    projection = build_semantic_projection(
        trace,
        certificate_mode="HandoffSafeCertificate",
        resolved_evidence=evidence,
    )
    source_path = tmp_path / "case" / "handoff-mut-src.json"
    mutated = deepcopy(handoff)
    mutated["delegated_capabilities"] = [
        _capability("cap:file-read"),
        _capability("cap:handoff"),
    ]
    mutated["signature_or_digest"] = canonical_hash(mutated)
    _write_json(source_path, mutated)
    assert delegated_capability_ids(handoff) != delegated_capability_ids(mutated)
    with pytest.raises(EvidenceResolutionError, match="fidelity"):
        assert_handoff_capability_fidelity(
            source_handoffs=[mutated],
            projected_handoffs=projection_handoffs(projection),
            lean_capability_sequences=[delegated_capability_ids(handoff)],
        )


def test_cli_issuance_bundle_isolated_verify_and_lean(tmp_path: Path) -> None:
    if shutil.which("lake") is None:
        pytest.skip("lake not available for full Lean execution path")
    handoff = _make_handoff(handoff_id="handoff-cli", delegated=["cap:handoff"])
    trace_path, _trace = _prepare_case(
        tmp_path, handoffs=[handoff], selected_ids=["handoff-cli"]
    )
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
            str(trace_path),
            "--out",
            str(out_cert),
            "--result-out",
            str(result_out),
            "--certificate-mode",
            "HandoffSafeCertificate",
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
    assert cert["certificate_mode"] == "HandoffSafeCertificate"
    assert cert.get("lean_proof_checked") is True
    result_payload = _load(result_out)
    projection_path = Path(result_payload["artifact_paths"]["semantic_projection"])
    assert projection_path.is_file()
    projection = _load(projection_path)
    validate_artifact(projection, "PFCoreSemanticProjection.v0")
    lean_path = Path(result_payload["artifact_paths"]["generated_proof"])
    _assert_fidelity([handoff], projection, lean_path.read_text(encoding="utf-8"))

    bundle_dir = tmp_path / "bundle"
    bundle_release(trace_path, out_cert, bundle_dir, lean_check_result_path=result_out)
    assert validate_bundle(bundle_dir).ok

    isolated = tmp_path / "isolated" / "bundle"
    isolated.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundle_dir, isolated)
    assert validate_bundle(isolated).ok

    bind = subprocess.run(
        [
            sys.executable,
            "-m",
            "pcs_core.cli",
            "pf-core",
            "verify-proof-binding",
            "--certificate",
            str(out_cert),
            "--trace",
            str(trace_path),
        ],
        cwd=REPO / "python",
        capture_output=True,
        text=True,
        check=False,
    )
    assert bind.returncode == 0, bind.stderr + bind.stdout


def test_handoff_safe_requires_explicit_selection(tmp_path: Path) -> None:
    handoff = _make_handoff(handoff_id="handoff-need-sel", delegated=["cap:handoff"])
    work = tmp_path / "case"
    work.mkdir()
    trace = dict(_load(FILE_READ))
    trace_path = work / "trace.json"
    _write_json(trace_path, trace)
    _write_json(work / "handoff-need-sel.json", handoff)
    with pytest.raises(EvidenceResolutionError, match="handoff_ids"):
        resolve_pf_core_evidence(
            trace,
            trace_path=trace_path,
            certificate_mode="HandoffSafeCertificate",
        )


def test_legacy_fixture_handoff_still_usable_with_selection(tmp_path: Path) -> None:
    handoff = _load(HANDOFF_FIXTURE)
    # Fixture from_principal only lists cap:handoff; keep that.
    trace_path, trace = _prepare_case(
        tmp_path, handoffs=[handoff], selected_ids=[str(handoff["handoff_id"])]
    )
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=trace_path,
        certificate_mode="HandoffSafeCertificate",
    )
    assert "cap:handoff" in generated.path.read_text(encoding="utf-8")


def test_missing_selection_still_errors_in_codegen(tmp_path: Path) -> None:
    trace = dict(_load(FILE_READ))
    trace_file = tmp_path / "trace.json"
    _write_json(trace_file, trace)
    with pytest.raises(CertificateModeEvidenceMissing, match="handoff_ids"):
        generate_proof_obligation_file(
            trace,
            tmp_path / "out",
            trace_path=trace_file,
            certificate_mode="HandoffSafeCertificate",
        )
