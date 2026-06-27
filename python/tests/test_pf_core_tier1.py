"""Tier 1 PF-Core tests: semantics_layer, PCS envelope path, cross-language vectors."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pcs_core.hash import canonical_hash
from pcs_core.lean_check import PCS_LEAN_CHECK_DISCLAIMER
from pcs_core.pf_core_certifyedge import (
    CERTIFYEDGE_INSTALL_DOC,
    certifyedge_cli_available,
    certifyedge_mock_enabled,
)
from pcs_core.pf_core_contract import (
    load_contract,
    resolve_semantics_layer,
    validate_trace_contracts,
)
from pcs_core.pf_core_contract_semantics import (
    build_contract_semantics_checked,
    default_semantics_layer_for_contract,
    validate_semantics_layer,
)
from pcs_core.pf_core_runtime import validate_denied_events_preserved, validate_pfcore_trace_hash_chain

REPO = Path(__file__).resolve().parents[2]
CONTRACT_VALID = REPO / "examples" / "pf-core-valid" / "contract_checked"
INVALID_VECTORS = REPO / "python" / "tests" / "hash_vectors" / "pf_core" / "invalid"
PROOF_OBLIGATION = REPO / "examples" / "proof_obligation.valid.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_checked_has_semantics_layer() -> None:
    contract = load_contract(CONTRACT_VALID / "contract.json")
    assert "semantics_layer" in contract
    layers = resolve_semantics_layer(contract)
    assert layers["require_capability"] == "lean"
    assert layers["require_decision"] == "lean"
    assert layers["require_trace_safe"] == "lean"


def test_default_semantics_layer_matches_contract_semantics_doc() -> None:
    contract = {
        "pre": {
            "require_capability": "cap:file-read",
            "require_role": "agent",
        },
        "post": {"require_decision": "allow"},
        "invariant": {"require_trace_safe": True},
    }
    layers = default_semantics_layer_for_contract(contract)
    assert layers["require_capability"] == "lean"
    assert layers["require_role"] == "runtime"
    assert layers["require_decision"] == "lean"
    assert layers["require_trace_safe"] == "lean"


def test_semantics_layer_orphan_field_rejected() -> None:
    contract = _load(CONTRACT_VALID / "contract.json")
    contract = dict(contract)
    contract.pop("signature_or_digest", None)
    contract["semantics_layer"] = {"require_role": "runtime"}
    issues = validate_semantics_layer(contract)
    assert any(issue.code == "SemanticsLayerOrphanField" for issue in issues)


def test_semantics_layer_out_of_scope_active_field_rejected() -> None:
    contract = _load(CONTRACT_VALID / "contract.json")
    contract = dict(contract)
    contract.pop("signature_or_digest", None)
    contract["semantics_layer"] = {"require_capability": "out_of_scope"}
    issues = validate_semantics_layer(contract)
    assert any(issue.code == "SemanticsLayerOutOfScopeFieldSet" for issue in issues)


def test_build_contract_semantics_checked_uses_semantics_layer() -> None:
    trace = _load(CONTRACT_VALID / "trace.json")
    contract = load_contract(CONTRACT_VALID / "contract.json")
    checked = build_contract_semantics_checked(trace, {contract["contract_id"]: contract})
    assert "contract-file-read-v0.pre.require_capability" in checked["lean"]
    assert checked["runtime"] == []


def test_contract_semantics_checked_excludes_runtime_only_fields() -> None:
    contract = _load(CONTRACT_VALID / "contract.json")
    contract = dict(contract)
    contract.pop("signature_or_digest", None)
    contract["pre"]["require_role"] = "agent"
    contract["semantics_layer"] = resolve_semantics_layer(contract)
    contract["semantics_layer"]["require_role"] = "runtime"
    contract["signature_or_digest"] = canonical_hash(
        {k: v for k, v in contract.items() if k != "signature_or_digest"}
    )
    trace = _load(CONTRACT_VALID / "trace.json")
    checked = build_contract_semantics_checked(trace, {contract["contract_id"]: contract})
    assert "contract-file-read-v0.pre.require_role" in checked["runtime"]


def test_negative_hash_chain_vector_python() -> None:
    trace = _load(INVALID_VECTORS / "trace_hash_chain_break.json")
    errors = validate_pfcore_trace_hash_chain(trace)
    assert any("EventHashMismatch" in err for err in errors)


def test_negative_claim_class_overclaim_vector_python() -> None:
    trace = _load(INVALID_VECTORS / "claim_class_overclaim_trace.json")
    errors = validate_pfcore_trace_hash_chain(trace)
    assert any("ClaimClassOverclaim" in err for err in errors)


def test_negative_contract_violation_vector_python() -> None:
    root = INVALID_VECTORS / "contract_capability_missing"
    trace = _load(root / "trace.json")
    contract = _load(root / "contract.json")
    issues = validate_trace_contracts(trace, {contract["contract_id"]: contract})
    assert any(issue.code == "ContractCapabilityRequired" for issue in issues)


def test_negative_denied_event_dropped_vector_python() -> None:
    root = INVALID_VECTORS / "denied_event_dropped"
    tool_use = _load(root / "tool_use_trace.json")
    pfcore = _load(root / "pfcore_trace.json")
    with pytest.raises(Exception) as exc:
        validate_denied_events_preserved(tool_use, pfcore)
    assert "DroppedDeniedEvent" in str(exc.value)


def test_pcs_lean_check_disclaimer_never_mentions_lean_kernel_checked() -> None:
    combined = PCS_LEAN_CHECK_DISCLAIMER.lower()
    assert "leankernelchecked" not in combined.replace("_", "").replace("-", "")


def test_pcs_envelope_check_alias_runs_same_as_lean_check(tmp_path: Path) -> None:
    if not PROOF_OBLIGATION.is_file():
        pytest.skip("proof_obligation.valid.json missing")
    out = tmp_path / "lean_check_result.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pcs_core.cli",
            "pcs-envelope",
            "check",
            "--obligations",
            str(PROOF_OBLIGATION),
            "--out",
            str(out),
            "--skip-lean-build",
        ],
        cwd=REPO / "python",
        capture_output=True,
        text=True,
    )
    assert result.returncode in {0, 1}
    assert out.is_file()
    payload = _load(out)
    assert payload.get("check_id")
    assert payload.get("status") in {"ProofChecked", "Rejected", "Stale"}
    assert "LeanKernelChecked" not in (result.stdout + result.stderr)


def test_pcs_lean_check_prints_deprecation_notice(tmp_path: Path) -> None:
    if not PROOF_OBLIGATION.is_file():
        pytest.skip("proof_obligation.valid.json missing")
    out = tmp_path / "lean_check_result.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pcs_core.cli",
            "lean-check",
            "--obligations",
            str(PROOF_OBLIGATION),
            "--out",
            str(out),
            "--skip-lean-build",
        ],
        cwd=REPO / "python",
        capture_output=True,
        text=True,
    )
    assert "pcs-envelope check" in result.stderr
    assert "LeanKernelChecked" not in (result.stdout + result.stderr)


def test_certifyedge_install_doc_present() -> None:
    assert "certifyedge" in CERTIFYEDGE_INSTALL_DOC.lower()
    assert certifyedge_mock_enabled() or isinstance(certifyedge_cli_available(), bool)
