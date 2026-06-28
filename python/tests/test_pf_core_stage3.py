"""Tests for PF-Core Stage 3 Lean kernel and lean-check integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.lean_catalog import PF_CORE_THEOREM_CATALOG
from pcs_core.lean_check import (
    LEAN_CHECK_DISCLAIMER,
    PF_CORE_ASSUMPTION_REFS,
    audit_pfcore_lean_no_sorry,
    check_pfcore_trace_lean_semantics,
    event_safe_d,
    run_pfcore_lean_check,
    trace_safe_d,
)
from pcs_core.pf_core_claims import (
    audit_boundary,
    audit_claims,
    audit_lean_catalog,
)
from pcs_core.pf_core_runtime import (
    compile_tool_use_trace_to_pfcore_trace,
    expand_principal_capabilities,
    principal_capabilities_explicit,
)
from pcs_core.validate import validate_file

REPO = Path(__file__).resolve().parents[2]

VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"

TOOL_USE_TRACE = (
    REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "tool_use_trace.json"
)

PF_CORE_LEAN = REPO / "lean" / "PFCore"


def _load(path: Path) -> dict:

    return json.loads(path.read_text(encoding="utf-8"))


def test_pfcore_lean_directory_exists() -> None:

    assert PF_CORE_LEAN.is_dir()

    expected = {
        "Basic.lean",
        "Principal.lean",
        "Capability.lean",
        "Resource.lean",
        "Action.lean",
        "Event.lean",
        "Trace.lean",
        "Contract.lean",
        "Handoff.lean",
        "Certificate.lean",
        "Soundness.lean",
        "Theorems.lean",
        "TraceCheck.lean",
    }

    assert expected <= {path.name for path in PF_CORE_LEAN.glob("*.lean")}


def test_pfcore_lean_catalog_matches_sources() -> None:

    errors = audit_lean_catalog()

    assert errors == [], f"PF-Core lean catalog audit failed: {errors}"


def test_pfcore_catalog_includes_trace_safety_theorems() -> None:

    required = {
        "traceSafeD_sound",
        "allowed_event_has_allowed_action",
        "every_allowed_event_in_safe_trace_is_allowed",
        "handoff_does_not_expand_authority",
    }

    assert required <= PF_CORE_THEOREM_CATALOG


def test_no_sorry_audit_passes() -> None:

    assert audit_pfcore_lean_no_sorry() == []


def test_valid_trace_passes_event_and_trace_deciders() -> None:

    trace = _load(VALID_TRACE)

    events = trace["events"]

    assert all(event_safe_d(event) for event in events)

    assert trace_safe_d(events)

    assert check_pfcore_trace_lean_semantics(trace) == []


def test_unsafe_allow_event_fails_decider() -> None:

    trace = _load(VALID_TRACE)

    event = dict(trace["events"][0])

    event["decision"] = "allow"

    event["principal"] = dict(event["principal"])

    event["principal"]["capabilities"] = []

    event["principal"]["roles"] = []

    assert not event_safe_d(event)


def test_role_expansion_produces_explicit_capabilities_in_compiled_trace() -> None:

    tool_use_trace = _load(TOOL_USE_TRACE)

    compiled = compile_tool_use_trace_to_pfcore_trace(tool_use_trace)

    expected_caps = expand_principal_capabilities({"roles": ["agent"], "capabilities": []})

    for event in compiled["events"]:
        principal = event["principal"]

        assert principal["capabilities"] == expected_caps

        assert principal_capabilities_explicit(principal)


def test_roles_without_explicit_capabilities_fail_lean_semantics() -> None:

    trace = _load(VALID_TRACE)

    event = dict(trace["events"][0])

    principal = dict(event["principal"])

    principal["capabilities"] = []

    event["principal"] = principal

    mutated = dict(trace)

    mutated["events"] = [event]

    issues = check_pfcore_trace_lean_semantics(mutated)

    assert any(issue.code == "PrincipalCapabilityMismatch" for issue in issues)


@pytest.mark.parametrize("skip_build", [True])
def test_pfcore_lean_check_emits_runtime_checked_when_build_skipped(
    tmp_path: Path, skip_build: bool
) -> None:

    out = tmp_path / "PFCoreCertificate.v0.json"

    code, result = run_pfcore_lean_check(VALID_TRACE, out_path=out, skip_build=skip_build)

    assert code == 0, result

    assert result["status"] == "DecidersPassed"

    assert result["claim_class"] == "RuntimeChecked"

    assert result["disclaimer"] == LEAN_CHECK_DISCLAIMER

    assert result["theorems_checked"] == sorted(PF_CORE_THEOREM_CATALOG)

    assert result["assumption_refs"] == PF_CORE_ASSUMPTION_REFS

    cert = json.loads(out.read_text(encoding="utf-8"))

    assert cert["artifact_type"] == "PFCoreCertificate.v0"

    assert cert["claim_class"] == "RuntimeChecked"

    assert cert["theorems_checked"] == sorted(PF_CORE_THEOREM_CATALOG)

    assert cert["disclaimer"] == LEAN_CHECK_DISCLAIMER

    assert "proof_ref" not in cert


def test_pfcore_lean_check_never_emits_unqualified_proof_checked(tmp_path: Path) -> None:

    _, result = run_pfcore_lean_check(VALID_TRACE, out_path=tmp_path / "cert.json", skip_build=True)

    assert result["status"] != "ProofChecked"

    assert result["claim_class"] in {"RuntimeChecked", "LeanKernelChecked"}


def test_pf_core_full_pipeline_on_valid_tool_use_example(tmp_path: Path) -> None:

    assert audit_claims() == []

    assert audit_boundary() == []

    assert audit_lean_catalog() == []

    assert audit_pfcore_lean_no_sorry() == []

    tool_use_trace = _load(TOOL_USE_TRACE)

    compiled = compile_tool_use_trace_to_pfcore_trace(tool_use_trace)

    validate_file(VALID_TRACE)

    compiled_path = tmp_path / "compiled_trace.json"

    compiled_path.write_text(json.dumps(compiled, indent=2), encoding="utf-8")

    validate_file(compiled_path)

    out = tmp_path / "PFCoreCertificate.v0.json"

    code, result = run_pfcore_lean_check(compiled_path, out_path=out, skip_build=True)

    assert code == 0, result

    assert result["claim_class"] == "RuntimeChecked"

    validate_file(out)


def test_lakefile_declares_pfcore_target() -> None:

    lakefile = (REPO / "lean" / "lakefile.lean").read_text(encoding="utf-8")

    assert "lean_lib PFCore" in lakefile

    assert "PFCore" in lakefile


def test_pcs_root_module_exists() -> None:

    assert (REPO / "lean" / "PCS.lean").is_file()
