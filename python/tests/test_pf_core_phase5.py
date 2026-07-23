"""Tests for PF-Core Phase 5 runtime semantics (observed effects, deny-closed, naming)."""

from __future__ import annotations

from pathlib import Path

from pcs_core.lean_catalog import PF_CORE_THEOREM_CATALOG
from pcs_core.pf_core_runtime import (
    validate_event_safe_deny_closed,
    validate_observed_effects_agree,
    validate_tenant_projection_isolation,
)

REPO = Path(__file__).resolve().parents[2]

PHASE5_MODULES = (
    "Hash.lean",
    "ObservedEffect.lean",
    "DenyClosed.lean",
    "PairedExecution.lean",
)

PHASE5_THEOREMS = frozenset(
    {
        "observed_sensitive_effects_in_frame",
        "accepted_transition_no_undeclared_sensitive_observation",
        "eventSafeDenyClosed_implies_eventSafe",
        "traceSafeDenyClosed_implies_traceSafe",
        "traceSafe_implies_tenant_projection_isolation",
        "trace_append_preserves_tenant_projection_isolation",
        "tenantProjectionIsolationD_sound",
    }
)


def _lean_source(name: str) -> str:
    path = REPO / "lean" / "PFCore" / name
    assert path.is_file(), f"missing Lean module: {path}"
    return path.read_text(encoding="utf-8")


def test_phase5_modules_exist_without_sorry() -> None:
    for module in PHASE5_MODULES:
        text = _lean_source(module)
        for token in ("sorry", "admit", "axiom", "unsafe"):
            assert token not in text, f"{token} found in {module}"


def test_phase5_theorems_in_catalog() -> None:
    missing = PHASE5_THEOREMS - PF_CORE_THEOREM_CATALOG
    assert not missing, f"missing from PF_CORE_THEOREM_CATALOG: {sorted(missing)}"


def test_observed_effect_structure_present() -> None:
    text = _lean_source("ObservedEffect.lean")
    for name in (
        "structure ObservedEffect",
        "def TrustedInstrumentation",
        "theorem observed_sensitive_effects_in_frame",
        "theorem accepted_transition_no_undeclared_sensitive_observation",
        "TrustedInstrumentation",
    ):
        assert name in text, f"missing {name}"


def test_deny_closed_refinement_present() -> None:
    text = _lean_source("DenyClosed.lean")
    for name in (
        "def EventSafeDenyClosed",
        "def DenyPathClosed",
        "def NoToolInvocationAfterDenial",
        "def NoDelegatedAuthorityOnDeny",
        "def DenyReasonConsistent",
        "theorem eventSafeDenyClosed_implies_eventSafe",
        "theorem traceSafeDenyClosed_implies_traceSafe",
    ):
        assert name in text, f"missing {name}"


def test_tenant_projection_isolation_naming() -> None:
    obs = _lean_source("Observational.lean")
    assert "def TenantProjectionIsolation" in obs
    assert "abbrev NonInterference := TenantProjectionIsolation" in obs
    assert "theorem traceSafe_implies_tenant_projection_isolation" in obs
    paired = _lean_source("PairedExecution.lean")
    assert "def PairedExecutionNonInterference" in paired
    assert "not proved" in paired.lower() or "unproved" in paired.lower()
    assert "Research scaffolding" in paired or "research scaffolding" in paired.lower()


def test_runtime_semantics_doc() -> None:
    doc = (REPO / "docs" / "pf-core" / "runtime-semantics.md").read_text(encoding="utf-8")
    for phrase in (
        "TrustedInstrumentation",
        "TenantProjectionIsolation",
        "EventSafeDenyClosed",
        "PairedExecutionNonInterference",
        "instrumentation",
    ):
        assert phrase in doc, f"missing {phrase!r} in runtime-semantics.md"
    assert "not proved" in doc.lower() or "unproved" in doc.lower()


def test_non_interference_doc_prefers_tenant_projection_isolation() -> None:
    doc = (REPO / "docs" / "pf-core" / "non-interference.md").read_text(encoding="utf-8")
    assert "TenantProjectionIsolation" in doc
    assert "PairedExecutionNonInterference" in doc
    assert "compatibility alias" in doc.lower()


def test_validate_observed_effects_agree() -> None:
    action = {
        "effects": [{"effect_kind": "file.read"}, {"effect_kind": "file.write"}],
        "reads": [{"uri": "/data/a", "tenant": "t"}],
        "writes": [{"uri": "/data/b", "tenant": "t"}],
    }
    ok = [{"kind": "file.write", "resource": {"uri": "/data/b"}}]
    assert validate_observed_effects_agree(action, ok) == []
    bad = [{"kind": "network.egress"}]
    errors = validate_observed_effects_agree(action, bad)
    assert any("not in declared" in e for e in errors)


def test_validate_event_safe_deny_closed() -> None:
    clean = {
        "events": [
            {
                "decision": "deny",
                "action": {
                    "effects": [{"effect_kind": "file.read"}],
                    "writes": [],
                    "reads": [],
                },
            }
        ]
    }
    assert validate_event_safe_deny_closed(clean) == []
    dirty = {
        "events": [
            {
                "decision": "deny",
                "action": {
                    "effects": [{"effect_kind": "file.write"}],
                    "writes": [{"uri": "/data/x", "tenant": "t"}],
                    "reads": [],
                },
            }
        ]
    }
    errors = validate_event_safe_deny_closed(dirty)
    assert len(errors) >= 2


def test_validate_tenant_projection_isolation_alias() -> None:
    trace = {
        "events": [
            {
                "decision": "allow",
                "principal": {"tenant": "alpha"},
                "action": {"reads": [], "writes": []},
            }
        ]
    }
    assert validate_tenant_projection_isolation(trace, "alpha", "beta") == []
