"""Tests for PF-Core Stage 1 trust boundary."""

from __future__ import annotations

import pytest

from pcs_core.pf_core_claims import audit_boundary, audit_claims, audit_lean_catalog
from pcs_core.registry_data import pf_core_artifact_types, registry_entries
from pcs_core.validate import detect_artifact_type


def test_pf_core_registry_entries() -> None:
    entries = registry_entries()
    assert len(pf_core_artifact_types()) == 10
    assert "AssumptionSet.v0" in entries
    assert len(entries) > len(pf_core_artifact_types())
    trace = entries["PFCoreTrace.v0"]
    assert trace["schema_owner"] == "pcs-core"
    assert trace["release_mode_required"] is True
    principal = entries["PFCorePrincipal.v0"]
    assert principal["release_mode_required"] is False


def test_pf_core_artifact_types_set() -> None:
    types = pf_core_artifact_types()
    assert "PFCoreTrace.v0" in types
    assert "PFCoreCertificate.v0" in types
    assert "PFCoreRuntimeObservation.v0" in types


def test_explicit_artifact_type_requires_schema_const() -> None:
    data = {"artifact_type": "ClaimArtifact.v0", "artifact_id": "x"}
    assert detect_artifact_type(data) == "ClaimArtifact.v0"


def test_explicit_artifact_type_rejected_without_schema_const() -> None:
    data = {"artifact_type": "PFCoreTrace.v0", "trace_id": "t-1"}
    assert detect_artifact_type(data) == "PFCoreTrace.v0"


def test_audit_claims_passes_repo_docs() -> None:
    assert audit_claims() == []


def test_audit_boundary_passes() -> None:
    assert audit_boundary() == []


def test_audit_lean_catalog_passes() -> None:
    errors = audit_lean_catalog()
    assert errors == [], f"lean catalog audit failed: {errors}"


def test_forbidden_phrase_detected(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pcs_core import pf_core_claims

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "bad.md").write_text("This agent is safe forever.\n", encoding="utf-8")

    monkeypatch.setattr(pf_core_claims, "_scan_roots", lambda: [docs])
    violations = audit_claims()
    assert len(violations) == 1
    assert violations[0].phrase == "agent is safe"


def test_trusted_catalog_includes_tool_use_and_witness_theorems() -> None:
    from pcs_core.lean_catalog import (
        LEAN_THEOREM_CATALOG,
        UNTRUSTED_LEAN_THEOREM_CATALOG,
    )

    assert "tool_trace_hash_matches_certificate" in LEAN_THEOREM_CATALOG
    assert "witness_result_hashes_admissible" in LEAN_THEOREM_CATALOG
    assert "tool_trace_hash_matches_certificate" not in UNTRUSTED_LEAN_THEOREM_CATALOG


def test_lean_check_disclaimer_constant() -> None:
    from pcs_core.lean_check import LEAN_CHECK_DISCLAIMER, PCS_LEAN_CHECK_DISCLAIMER

    assert "LeanKernelChecked" in LEAN_CHECK_DISCLAIMER
    assert "concrete Lean proof" in LEAN_CHECK_DISCLAIMER
    assert "not Lean-backed" in PCS_LEAN_CHECK_DISCLAIMER
    assert "pf-core lean-check" in PCS_LEAN_CHECK_DISCLAIMER
