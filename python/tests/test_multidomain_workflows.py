"""Multi-domain workflow profile, tool-use, and computation conformance tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.conformance import build_conformance_report_data, list_suites, run_conformance
from pcs_core.paths import examples_dir
from pcs_core.registry import build_artifact_registry, registry_entries
from pcs_core.tool_use_validate import (
    policy_hash_from_policy_id,
    validate_tool_use_invalid_case,
    validate_tool_use_release_directory,
    validate_tool_use_trace_certificate_alignment,
)
from pcs_core.validate import validate_artifact, validate_file

ROOT = Path(__file__).resolve().parents[2]


def test_workflow_profile_artifacts_registered() -> None:
    entries = registry_entries()
    assert "WorkflowProfile.v0" in entries
    assert "ToolUseTrace.v0" in entries
    assert "ToolUseCertificate.v0" in entries
    assert "ComputationWitness.v0" in entries
    assert "DatasetReceipt.v0" in entries


def test_computation_witness_semantic_checks_present() -> None:
    checks = registry_entries()["ComputationWitness.v0"]["semantic_checks"]
    check_ids = {check["check_id"] for check in checks}
    assert check_ids == {
        "dataset_hash_matches_receipt",
        "environment_hash_matches_receipt",
        "run_receipt_hash_matches_declared_run",
        "result_hashes_match_result_artifacts",
        "code_commit_present",
        "computation_status_checked_for_release",
        "source_commit_matches_release_manifest",
        "signature_or_digest_valid",
    }


def test_tool_use_certificate_semantic_checks_present() -> None:
    checks = registry_entries()["ToolUseCertificate.v0"]["semantic_checks"]
    check_ids = {check["check_id"] for check in checks}
    assert check_ids == {
        "tool_trace_hash_matches_certificate",
        "certificate_status_checked_for_release",
        "policy_hash_matches_certificate",
        "no_unauthorized_tool_calls",
        "source_commit_matches_release_manifest",
        "signature_or_digest_valid",
    }


def test_workflow_profile_examples_validate() -> None:
    for name in (
        "labtrust_qc_release.valid.json",
        "agent_tool_use_safety.valid.json",
        "scientific_computation_reproducibility.valid.json",
    ):
        assert validate_file(examples_dir() / "workflow_profiles" / name) == "WorkflowProfile.v0"


def test_tool_use_release_directory_validates() -> None:
    errors = validate_tool_use_release_directory(examples_dir() / "tool-use-release")
    assert errors == [], errors


def test_tool_use_trace_certificate_alignment() -> None:
    release = examples_dir() / "tool-use-release"
    trace = json.loads((release / "tool_use_trace.valid.json").read_text(encoding="utf-8"))
    cert = json.loads((release / "tool_use_certificate.valid.json").read_text(encoding="utf-8"))
    assert validate_tool_use_trace_certificate_alignment(trace, cert) == []
    assert cert["policy_hash"] == policy_hash_from_policy_id(str(trace["policy_id"]))


@pytest.mark.parametrize(
    "case",
    [
        "unauthorized_tool_call",
        "missing_policy_hash",
        "mismatched_tool_trace_hash",
        "rejected_tool_certificate",
        "unknown_tool_authorization_status",
    ],
)
def test_tool_use_invalid_cases_fail(case: str) -> None:
    case_dir = examples_dir() / "tool-use-release-invalid" / case
    if not case_dir.is_dir():
        pytest.skip("run python/scripts/materialize_tool_use_fixtures.py")
    assert validate_tool_use_invalid_case(case_dir) == []


def test_multidomain_conformance_suite_passes() -> None:
    if not (examples_dir() / "computation-release" / "computation_witness.json").is_file():
        pytest.skip("run python/scripts/materialize_computation_fixtures.py")
    if not (examples_dir() / "tool-use-release" / "tool_use_trace.valid.json").is_file():
        pytest.skip("run python/scripts/materialize_tool_use_fixtures.py")
    code, errors = run_conformance("multidomain")
    assert code == 0, errors
    report = build_conformance_report_data("multidomain")
    validate_artifact(report, "ConformanceReport.v0")
    assert report["status"] == "passed"


def test_new_conformance_suites_listed() -> None:
    names = list_suites()
    assert "workflow-profile" in names
    assert "tool-use" in names
    assert "computation" in names
    assert "multidomain" in names


def test_built_registry_includes_workflow_profile() -> None:
    registry = build_artifact_registry()
    assert "WorkflowProfile.v0" in registry["entries"]


def test_tool_use_hash_vectors_in_shared_catalog() -> None:
    from pcs_core.shared_hash_vectors import VECTOR_SPECS, verify_shared_vectors

    for artifact_type in ("WorkflowProfile.v0", "ToolUseTrace.v0", "ToolUseCertificate.v0"):
        assert artifact_type in VECTOR_SPECS
    assert verify_shared_vectors() == []


def test_computation_hash_vectors_in_shared_catalog() -> None:
    from pcs_core.shared_hash_vectors import VECTOR_SPECS, verify_shared_vectors

    for artifact_type in (
        "DatasetReceipt.v0",
        "EnvironmentReceipt.v0",
        "ComputationRunReceipt.v0",
        "ResultArtifact.v0",
        "ComputationWitness.v0",
    ):
        assert artifact_type in VECTOR_SPECS
    assert verify_shared_vectors() == []


def test_examples_check_includes_workflow_profiles() -> None:
    from pcs_core.validate import check_valid_examples

    check_valid_examples(examples_dir())
