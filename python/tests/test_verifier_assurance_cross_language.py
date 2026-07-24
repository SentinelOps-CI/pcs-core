"""Cross-language Verifier Assurance (PCS-VA-07) parity.

Python is the reference for semantics and report verify; Rust/TS must emit the
same error codes on shared fixtures and match shared hash vectors.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from pcs_core.hash import canonical_hash
from pcs_core.validate import ARTIFACT_SCHEMAS, detect_artifact_type, validate_semantics
from pcs_core.verifier_assurance_report import verify_assurance_report
from pcs_core.verifier_assurance_validate import (
    SemanticIssue,
    validate_va_semantics,
)

REPO = Path(__file__).resolve().parents[2]
VA_ROOT = REPO / "examples" / "verifier_assurance"
TS_SCHEMAS = REPO / "typescript" / "packages" / "core" / "src" / "schema.ts"
RUST_SCHEMAS = REPO / "rust" / "crates" / "pcs-core" / "src" / "validation.rs"

VA_CORE_TYPES = (
    "VerifierProfile.v1",
    "VerificationResult.v1",
    "RewardEvidenceEnvelope.v1",
    "OptimizationCampaignManifest.v1",
    "AdjudicationRecord.v1",
    "VerifierAssuranceReport.v1",
)

INVALID_CASES: tuple[tuple[str, str], ...] = (
    ("invalid/timeout_accept", "FailClosedDecision"),
    ("invalid/accept_mandatory_failure", "AcceptWithMandatoryFailure"),
    ("invalid/identical_normalization_digests", "IdenticalNormalizationDigests"),
    ("invalid/reward_total_mismatch", "RewardCompositionMismatch"),
    ("invalid/revoked_profile_active_reward", "RevokedProfileGate"),
    ("invalid/missing_rationale_commitment", "RationaleCommitment"),
    ("invalid/short_source_commit", "InvalidSourceCommit"),
    ("invalid/release_grade_no_adjudication", "ReleaseGradeAdjudication"),
    ("invalid/optimization_gap_missing_cohort", "OptimizationGapCohorts"),
    ("invalid/cohort_missing_access", "CohortAccessClass"),
    ("invalid/cohort_count_mismatch", "CohortCountMismatch"),
    ("invalid/excluded_items_invisible", "ExcludedItemsVisible"),
    ("invalid/missing_ci_method", "CIMethodsDeclared"),
    ("invalid/indeterminate_misclassification", "IndeterminateMisclassification"),
    ("invalid/active_reward_unresolved", "ActiveRewardUnresolvedClaims"),
    ("invalid/profile_digest_mismatch", "ProfileDigestMismatch"),
    ("invalid/reward_trajectory_mismatch", "RewardTrajectoryMismatch"),
    ("invalid/cross_artifact_version_mismatch", "CrossArtifactVersionMismatch"),
)

VALID_SINGLE_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("valid/profile_basic/profile.json", "VerifierProfile.v1"),
    ("valid/result_accept/result.json", "VerificationResult.v1"),
    ("valid/reward_scalar/reward.json", "RewardEvidenceEnvelope.v1"),
    ("valid/campaign_basic/campaign.json", "OptimizationCampaignManifest.v1"),
    ("valid/adjudication_basic/adjudication.json", "AdjudicationRecord.v1"),
    ("valid/report_rebuild/report.json", "VerifierAssuranceReport.v1"),
)


def _load(rel: str) -> dict:
    return json.loads((VA_ROOT / rel).read_text(encoding="utf-8"))


def _codes(issues: list) -> set[str]:
    out: set[str] = set()
    for item in issues:
        if isinstance(item, SemanticIssue):
            out.add(item.code)
        else:
            text = str(item)
            out.add(text.split(" at ", 1)[0] if " at " in text else text)
    return out


def _extract_quoted_types(path: Path, marker: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    block = text.split(marker, 1)[-1]
    patterns = (
        r'"(Verifier[^"]+\.v1)"',
        r'"(VerificationResult\.v1)"',
        r'"(RewardEvidenceEnvelope\.v1)"',
        r'"(OptimizationCampaignManifest\.v1)"',
        r'"(AdjudicationRecord\.v1)"',
    )
    found: set[str] = set()
    for pattern in patterns:
        found.update(re.findall(pattern, block))
    return found


def test_va_core_types_registered_python() -> None:
    for artifact_type in VA_CORE_TYPES:
        assert artifact_type in ARTIFACT_SCHEMAS


def test_va_core_types_registered_typescript() -> None:
    ts_types = _extract_quoted_types(TS_SCHEMAS, "const ARTIFACT_SCHEMAS")
    assert set(VA_CORE_TYPES).issubset(ts_types)


def test_va_core_types_registered_rust() -> None:
    rust_types = _extract_quoted_types(RUST_SCHEMAS, "const ARTIFACT_SCHEMAS")
    assert set(VA_CORE_TYPES).issubset(rust_types)


@pytest.mark.parametrize("rel,artifact_type", VALID_SINGLE_ARTIFACTS)
def test_va_valid_semantics_and_detection(rel: str, artifact_type: str) -> None:
    data = _load(rel)
    assert detect_artifact_type(data) == artifact_type
    assert validate_semantics(data, artifact_type) == []
    assert validate_va_semantics(data, artifact_type, as_issues=True) == []


@pytest.mark.parametrize("case_dir,expected_code", INVALID_CASES)
def test_va_invalid_semantics_codes(case_dir: str, expected_code: str) -> None:
    from pcs_core.verifier_assurance_validate import load_va_context_from_dir

    manifest = _load(f"{case_dir}/manifest.json")
    assert manifest["expected_error"] == expected_code
    artifact_file = str(manifest.get("artifact_file") or "artifact.json")
    artifact_type = str(manifest["artifact_type"])
    data = _load(f"{case_dir}/{artifact_file}")
    context = load_va_context_from_dir(VA_ROOT / case_dir)
    issues = validate_va_semantics(data, artifact_type, as_issues=True, context=context)
    assert expected_code in _codes(issues), issues


def test_va_unknown_field_rejected_by_schema() -> None:
    data = _load("invalid/unknown_field/artifact.json")
    from pcs_core.validate_detect import validate_schema

    errors = validate_schema(data, "VerifierProfile.v1")
    assert any("extra_field" in err or "Additional properties" in err for err in errors)


def test_va_verify_report_digest_parity() -> None:
    report = _load("valid/report_rebuild/report.json")
    assert verify_assurance_report(report) == []
    tampered = dict(report)
    tampered["report_id"] = "tampered-id"
    codes = _codes(verify_assurance_report(tampered))
    assert "ReportDigestMismatch" in codes


def test_va_shared_hash_vectors_exist() -> None:
    from pcs_core.shared_hash_vectors import VECTOR_SPECS, load_vector

    for artifact_type in VA_CORE_TYPES:
        assert artifact_type in VECTOR_SPECS
        vector = load_vector(artifact_type)
        input_rel = vector.get("input") or vector.get("input_file")
        assert isinstance(input_rel, str)
        data = json.loads((REPO / input_rel).read_text(encoding="utf-8"))
        assert canonical_hash(data) == vector["expected_digest"]


def test_rust_va_suite_passes() -> None:
    result = subprocess.run(
        ["cargo", "test", "--locked", "va_", "--", "--nocapture"],
        cwd=REPO / "rust",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
