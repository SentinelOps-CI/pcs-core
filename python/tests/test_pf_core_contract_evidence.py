"""PR3 contract evidence fidelity: semantics_layer projection + ContractChecked binding."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from pcs_core.hash import canonical_hash
from pcs_core.pf_core_bundle import bundle_release, validate_bundle
from pcs_core.pf_core_contract_semantics import (
    materialize_contract_semantics_layer,
    resolve_semantics_layer,
)
from pcs_core.pf_core_lean_codegen import (
    CertificateModeEvidenceMissing,
    generate_proof_obligation_file,
)
from pcs_core.pf_core_resolved_evidence import (
    EvidenceResolutionError,
    assert_contract_projection_ids,
    collect_contract_theorem_names,
    compute_contract_evidence_digest,
    contract_source_file_digests,
    resolve_pf_core_evidence,
)
from pcs_core.pf_core_semantic_projection import (
    build_semantic_projection,
    projection_contract_ids,
    projection_contracts,
)
from pcs_core.validate import validate_artifact

REPO = Path(__file__).resolve().parents[2]
CONTRACT_FIXTURE = REPO / "examples" / "pf-core-valid" / "contract_checked"
CONTRACT_TRACE = CONTRACT_FIXTURE / "trace.json"
CONTRACT_JSON = CONTRACT_FIXTURE / "contract.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _prepare_case(
    tmp_path: Path,
    *,
    selected_ids: list[str] | None,
    include_unrelated_sibling: bool = False,
    contract: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    work = tmp_path / "case"
    work.mkdir(parents=True, exist_ok=True)
    trace = dict(_load(CONTRACT_TRACE))
    if selected_ids is None:
        trace.pop("evidence_selection", None)
    else:
        trace["evidence_selection"] = {
            "policy": "explicit_ids",
            "policy_version": "v0",
            "contract_ids": selected_ids,
        }
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
    body = dict(contract) if contract is not None else _load(CONTRACT_JSON)
    _write_json(work / "contract.json", body)
    if include_unrelated_sibling:
        sibling = deepcopy(body)
        sibling["contract_id"] = "contract-unrelated-sibling-v0"
        sibling["name"] = "Unrelated sibling"
        sibling.pop("signature_or_digest", None)
        sibling["signature_or_digest"] = canonical_hash(sibling)
        _write_json(work / "contract-unrelated.json", sibling)
    return trace_path, trace


def test_semantics_layer_materialized_after_defaults() -> None:
    contract = _load(CONTRACT_JSON)
    layers = resolve_semantics_layer(contract)
    records = materialize_contract_semantics_layer(
        contract,
        contract_id="contract-file-read-v0",
        referencing_event_ids=["ev-file-read-1"],
        effective_layers=layers,
    )
    assert records
    by_field = {item["field"]: item for item in records}
    assert by_field["require_capability"]["effective_layer"] == "lean"
    assert by_field["require_capability"]["section"] == "pre"
    assert by_field["require_capability"]["normalized_value"] == "cap:file-read"
    assert by_field["require_capability"]["lean_theorem"].startswith("concrete_contract_pre_")
    assert by_field["require_trace_safe"]["effective_layer"] == "lean"
    assert by_field["require_trace_safe"]["lean_theorem"].startswith("concrete_trace_satisfies_")


def test_projection_uses_semantics_layer_not_field_semantics(tmp_path: Path) -> None:
    trace_path, trace = _prepare_case(tmp_path, selected_ids=["contract-file-read-v0"])
    evidence = resolve_pf_core_evidence(
        trace,
        trace_path=trace_path,
        certificate_mode="ContractCheckedCertificate",
    )
    projection = build_semantic_projection(
        trace,
        certificate_mode="ContractCheckedCertificate",
        resolved_evidence=evidence,
    )
    validate_artifact(projection, "PFCoreSemanticProjection.v0")
    contracts = projection_contracts(projection)
    projected = contracts["contract-file-read-v0"]
    assert "field_semantics" not in projected
    assert isinstance(projected["semantics_layer"], list)
    assert projected["semantics_layer"]
    lean_fields = [
        item for item in projected["semantics_layer"] if item["effective_layer"] == "lean"
    ]
    assert lean_fields
    assert all("lean_theorem" in item for item in lean_fields)


def test_contract_checked_requires_explicit_selection(tmp_path: Path) -> None:
    trace_path, trace = _prepare_case(tmp_path, selected_ids=None)
    with pytest.raises(EvidenceResolutionError, match="contract_ids"):
        resolve_pf_core_evidence(
            trace,
            trace_path=trace_path,
            certificate_mode="ContractCheckedCertificate",
        )


def test_unrelated_sibling_not_auto_selected(tmp_path: Path) -> None:
    trace_path, trace = _prepare_case(
        tmp_path,
        selected_ids=["contract-file-read-v0"],
        include_unrelated_sibling=True,
    )
    evidence = resolve_pf_core_evidence(
        trace,
        trace_path=trace_path,
        certificate_mode="ContractCheckedCertificate",
    )
    assert evidence.selected_contract_ids == ("contract-file-read-v0",)
    assert "contract-unrelated-sibling-v0" not in evidence.contracts_by_id
    projection = build_semantic_projection(
        trace,
        certificate_mode="ContractCheckedCertificate",
        resolved_evidence=evidence,
    )
    assert projection_contract_ids(projection) == ["contract-file-read-v0"]


def test_unresolved_contract_ref_rejected(tmp_path: Path) -> None:
    trace_path, trace = _prepare_case(tmp_path, selected_ids=["contract-file-read-v0"])
    for event in trace.get("events") or []:
        if isinstance(event, dict):
            event["contract_refs"] = ["contract-file-read-v0", "contract-missing-v0"]
    _write_json(trace_path, trace)
    with pytest.raises(EvidenceResolutionError, match="unresolved"):
        resolve_pf_core_evidence(
            trace,
            trace_path=trace_path,
            certificate_mode="ContractCheckedCertificate",
        )


def test_certificate_binds_digests_and_theorems(tmp_path: Path) -> None:
    trace_path, trace = _prepare_case(tmp_path, selected_ids=["contract-file-read-v0"])
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=trace_path,
        certificate_mode="ContractCheckedCertificate",
    )
    evidence = resolve_pf_core_evidence(
        trace,
        trace_path=trace_path,
        certificate_mode="ContractCheckedCertificate",
    )
    digests = contract_source_file_digests(evidence)
    assert digests
    theorem_names = collect_contract_theorem_names(generated.theorem_names)
    assert theorem_names
    assert any(name.startswith("concrete_contract_pre_") for name in theorem_names)
    digest = compute_contract_evidence_digest(
        selected_contract_ids=evidence.selected_contract_ids,
        contract_source_file_digests=digests,
        effective_layers=evidence.effective_contract_semantic_layers,
        contract_theorem_names=theorem_names,
    )
    assert digest.startswith("sha256:")
    assert_contract_projection_ids(
        selected_contract_ids=evidence.selected_contract_ids,
        projected_contract_ids=projection_contract_ids(generated.semantic_projection or {}),
    )


def test_missing_selection_still_errors_in_codegen(tmp_path: Path) -> None:
    work = tmp_path / "case"
    work.mkdir()
    trace = dict(_load(CONTRACT_TRACE))
    trace.pop("evidence_selection", None)
    trace_path = work / "trace.json"
    _write_json(trace_path, trace)
    shutil.copy2(CONTRACT_JSON, work / "contract.json")
    with pytest.raises(CertificateModeEvidenceMissing, match="contract_ids"):
        generate_proof_obligation_file(
            trace,
            tmp_path / "out",
            trace_path=trace_path,
            certificate_mode="ContractCheckedCertificate",
        )


def test_cli_issuance_bundle_and_semantic_validation(tmp_path: Path) -> None:
    if shutil.which("lake") is None:
        pytest.skip("lake not available for full Lean execution path")
    case = tmp_path / "case"
    shutil.copytree(CONTRACT_FIXTURE, case)
    trace_path = case / "trace.json"
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
            "ContractCheckedCertificate",
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
    assert cert["certificate_mode"] == "ContractCheckedCertificate"
    assert cert.get("lean_proof_checked") is True
    assert cert["selected_contract_ids"] == ["contract-file-read-v0"]
    assert cert["contract_source_file_digests"]
    assert str(cert["contract_evidence_digest"]).startswith("sha256:")
    assert cert["contract_theorem_names"]
    result_payload = _load(result_out)
    projection_path = Path(result_payload["artifact_paths"]["semantic_projection"])
    assert projection_path.is_file()
    projection = _load(projection_path)
    validate_artifact(projection, "PFCoreSemanticProjection.v0")
    assert projection_contract_ids(projection) == ["contract-file-read-v0"]
    for item in projection_contracts(projection)["contract-file-read-v0"]["semantics_layer"]:
        assert "effective_layer" in item
        assert "section" in item
        assert "field" in item
        assert "normalized_value" in item

    bundle_dir = tmp_path / "bundle"
    bundle_release(trace_path, out_cert, bundle_dir, lean_check_result_path=result_out)
    assert validate_bundle(bundle_dir).ok
