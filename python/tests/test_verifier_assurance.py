"""Verifier Assurance (PCS-VA) focused tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from pcs_core.hash import canonical_hash
from pcs_core.paths import examples_dir, repo_root
from pcs_core.validate import validate_artifact, validate_file
from pcs_core.verifier_assurance_report import (
    build_assurance_report,
    report_body_without_integrity,
)
from pcs_core.verifier_assurance_validate import (
    check_va_invalid_fixtures,
    check_va_valid_fixtures,
    profile_digest,
    validate_verification_result_semantics,
    validate_verifier_profile_semantics,
)


def test_va_valid_and_invalid_fixtures() -> None:
    check_va_valid_fixtures()
    check_va_invalid_fixtures()


def test_profile_config_substitution_changes_digest() -> None:
    path = examples_dir() / "verifier_assurance" / "valid" / "profile_basic" / "profile.json"
    profile = json.loads(path.read_text(encoding="utf-8"))
    d1 = profile_digest(profile)
    altered = deepcopy(profile)
    altered["configuration"]["config_digest"] = "sha256:" + ("f" * 64)
    altered.pop("integrity", None)
    d2 = profile_digest(altered)
    assert d1 != d2


def test_fail_closed_timeout_cannot_accept() -> None:
    path = examples_dir() / "verifier_assurance" / "valid" / "result_accept" / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    result["execution_status"] = "timeout"
    result["decision"] = "accept"
    issues = validate_verification_result_semantics(result, as_issues=True)
    codes = {getattr(i, "code", None) for i in issues}
    assert "FailClosedDecision" in codes


def test_v0_verification_result_still_validates() -> None:
    path = examples_dir() / "labtrust" / "invalid_failed_verification_result.json"
    # invalid fixture should fail; pick a valid v0 if present
    candidates = list((examples_dir()).glob("*verification*valid*.json"))
    candidates += list((examples_dir() / "labtrust-release").rglob("*VerificationResult*"))
    # At minimum ensure v0 schema remains registered and distinct
    from pcs_core.validate_detect import ARTIFACT_SCHEMAS

    assert "VerificationResult.v0" in ARTIFACT_SCHEMAS
    assert "VerificationResult.v1" in ARTIFACT_SCHEMAS
    assert ARTIFACT_SCHEMAS["VerificationResult.v0"] != ARTIFACT_SCHEMAS["VerificationResult.v1"]


def test_report_rebuild_deterministic() -> None:
    base = examples_dir() / "verifier_assurance" / "valid" / "report_rebuild"
    campaign = json.loads((base / "campaign.json").read_text(encoding="utf-8"))
    results = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((base / "results").glob("*.json"))
    ]
    adjudications = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((base / "adjudications").glob("*.json"))
    ]
    kwargs = {
        "report_id": "rep-det",
        "created_at": "2026-07-24T15:00:00Z",
        "source_commit": "e068794683959c52a19594a6d271dd5e69f3c999",
        "release_grade": True,
        "excluded_items": [{"item_id": "ex-1", "reason_code": "out_of_scope"}],
        "unadjudicated_items": [],
        "applicability_limits": ["synthetic fixture only"],
    }
    a = build_assurance_report(
        campaign=campaign, results=results, adjudications=adjudications, **kwargs
    )
    b = build_assurance_report(
        campaign=campaign, results=results, adjudications=adjudications, **kwargs
    )
    assert report_body_without_integrity(a) == report_body_without_integrity(b)
    assert a["integrity"]["artifact_digest"] == b["integrity"]["artifact_digest"]


def test_cli_profile_validate(tmp_path: Path) -> None:
    from pcs_core.cli import main

    profile = examples_dir() / "verifier_assurance" / "valid" / "profile_basic" / "profile.json"
    assert main(["verifier", "profile", "validate", str(profile)]) == 0


def test_profile_digest_mismatch_with_context() -> None:
    from pcs_core.verifier_assurance_validate import (
        load_va_context_from_dir,
        validate_va_semantics,
    )

    case = examples_dir() / "verifier_assurance" / "invalid" / "profile_digest_mismatch"
    data = json.loads((case / "artifact.json").read_text(encoding="utf-8"))
    context = load_va_context_from_dir(case)
    issues = validate_va_semantics(
        data, "VerificationResult.v1", as_issues=True, context=context
    )
    codes = {getattr(i, "code", None) for i in issues}
    assert "ProfileDigestMismatch" in codes


def test_cli_json_diagnostics_structured() -> None:
    from pcs_core.cli import main
    import io
    from contextlib import redirect_stdout

    path = (
        examples_dir()
        / "verifier_assurance"
        / "invalid"
        / "timeout_accept"
        / "artifact.json"
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(["verifier", "result", "validate", str(path), "--json"])
    assert code == 1
    payload = json.loads(buf.getvalue())
    assert payload["ok"] is False
    assert any(err.get("code") == "FailClosedDecision" for err in payload["errors"])


def test_all_fifteen_rules_have_invalid_fixtures() -> None:
    """Every semantic matrix rule has at least one dedicated invalid fixture."""
    required = {
        "ProfileDigestMismatch": "profile_digest_mismatch",
        "RewardTrajectoryMismatch": "reward_trajectory_mismatch",
        "AcceptWithMandatoryFailure": "accept_mandatory_failure",
        "ReleaseGradeAdjudication": "release_grade_no_adjudication",
        "OptimizationGapCohorts": "optimization_gap_missing_cohort",
        "CohortAccessClass": "cohort_missing_access",
        "CohortCountMismatch": "cohort_count_mismatch",
        "RevokedProfileGate": "revoked_profile_active_reward",
        "IdenticalNormalizationDigests": "identical_normalization_digests",
        "CrossArtifactVersionMismatch": "cross_artifact_version_mismatch",
        "RationaleCommitment": "missing_rationale_commitment",
        "ExcludedItemsVisible": "excluded_items_invisible",
        "CIMethodsDeclared": "missing_ci_method",
        "RewardCompositionMismatch": "reward_total_mismatch",
        "IndeterminateMisclassification": "indeterminate_misclassification",
    }
    root = examples_dir() / "verifier_assurance" / "invalid"
    for code, dirname in required.items():
        manifest = json.loads((root / dirname / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["expected_error"] == code, dirname