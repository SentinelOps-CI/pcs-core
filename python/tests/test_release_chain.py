"""PCS v0.1 LabTrust release-chain validation."""

import copy
import json
from pathlib import Path

import pytest

from pcs_core.paths import resolve_release_chain_directory
from pcs_core.release_canonical import (
    LABTRUST_RC_CERTIFICATE_ID,
    LABTRUST_RC_CERTIFIED_BUNDLE_HASH,
    LABTRUST_RC_CERTIFYEDGE_COMMIT,
    LABTRUST_RC_LABTRUST_GYM_COMMIT,
    LABTRUST_RC_PROVABILITY_FABRIC_COMMIT,
    LABTRUST_RC_SCIENTIFIC_MEMORY_COMMIT,
    LABTRUST_RC_TRACE_HASH,
)
from pcs_core.release_chain import validate_release_chain
from pcs_core.release_chain_report import build_release_chain_report
from pcs_core.release_fixtures import (
    MANIFEST_ARTIFACTS,
    release_dir,
    validate_release_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
INVALID_ROOT = ROOT / "examples" / "labtrust-release-invalid"
MANIFEST = release_dir() / "RELEASE_FIXTURE_MANIFEST.json"
INVALID_PLACEHOLDER = release_dir() / "invalid_placeholder_commit_manifest.json"
INVALID_CE = release_dir() / "invalid_mismatched_certifyedge_commit_manifest.json"
INVALID_PF = release_dir() / "invalid_mismatched_pf_commit_manifest.json"
INVALID_LT = release_dir() / "invalid_mismatched_labtrust_commit_manifest.json"


def _codes(path: Path) -> set[str]:
    return {issue.code for issue in validate_release_chain(path)}


def _invalid_dir(name: str) -> Path:
    return INVALID_ROOT / name


def test_validate_release_chain_reports_manifest_missing(tmp_path: Path) -> None:
    assert "manifest_missing" in _codes(tmp_path)


def test_resolve_release_chain_directory_from_python_relative_path() -> None:
    assert resolve_release_chain_directory(Path("examples/labtrust-release")) == release_dir()


def test_validate_release_chain_passes_on_current_rc() -> None:
    assert validate_release_chain(release_dir()) == []
    report = build_release_chain_report(release_dir())
    assert report["status"] == "passed"
    assert report["release_candidate"] == "pcs-v0.1.0-rc1"
    assert report["checks_passed"] == 30
    assert report["checks_failed"] == 0
    assert report["checked_artifacts"] == len(MANIFEST_ARTIFACTS)


def test_validate_release_chain_json_output_passes() -> None:
    report = build_release_chain_report(release_dir())
    assert report["status"] == "passed"


def test_validate_release_chain_json_is_schema_valid_result() -> None:
    from pcs_core.release_chain_report import build_release_chain_validation_result
    from pcs_core.validate import validate_artifact

    result = build_release_chain_validation_result(release_dir())
    validate_artifact(result, "ReleaseChainValidationResult.v0")


def test_canonical_rc_pin_values_in_manifest_and_artifacts() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["labtrust_gym_commit"] == LABTRUST_RC_LABTRUST_GYM_COMMIT
    assert manifest["certifyedge_commit"] == LABTRUST_RC_CERTIFYEDGE_COMMIT
    assert manifest["provability_fabric_commit"] == LABTRUST_RC_PROVABILITY_FABRIC_COMMIT
    assert manifest["scientific_memory_commit"] == LABTRUST_RC_SCIENTIFIC_MEMORY_COMMIT
    from pcs_core.release_fixtures import file_digest

    certified_path = release_dir() / "science_claim_bundle.certified.json"
    assert manifest["artifacts"]["science_claim_bundle.certified.json"] == file_digest(
        certified_path.read_bytes(),
    )
    release_manifest = json.loads(
        (release_dir() / "release_manifest.v0.json").read_text(encoding="utf-8"),
    )
    assert (
        release_manifest["chain_root"]["certified_bundle_hash"] == LABTRUST_RC_CERTIFIED_BUNDLE_HASH
    )

    trace_cert = json.loads((release_dir() / "trace_certificate.json").read_text())
    assert trace_cert["certificate_id"] == LABTRUST_RC_CERTIFICATE_ID
    assert trace_cert["trace_hash"] == LABTRUST_RC_TRACE_HASH

    trace = json.loads((release_dir() / "trace.json").read_text())
    assert trace["trace_hash"] == LABTRUST_RC_TRACE_HASH


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    [
        ("placeholder_commit", "placeholder_commit_detected"),
        ("mismatched_certificate_id", "certificate_id_mismatch"),
        ("mismatched_trace_hash", "trace_hash_mismatch"),
        ("mismatched_certified_bundle_hash", "verified_input_hash_mismatch"),
        ("failed_scientific_memory_import", "scientific_memory_import_failed"),
        ("legacy_import_mode", "legacy_import_detected"),
    ],
)
def test_validate_release_chain_rejects_invalid_fixtures(
    fixture_name: str,
    expected_code: str,
) -> None:
    path = _invalid_dir(fixture_name)
    if not path.is_dir():
        pytest.skip(f"invalid fixture not materialized: {path}")
    codes = _codes(path)
    assert expected_code in codes
    report = build_release_chain_report(path)
    assert report["status"] == "failed"
    assert report["failure_code"] == expected_code or expected_code in {
        f.get("failure_code") for f in report.get("failures", [])
    }


def test_validate_release_manifest_passes_on_current_fixture() -> None:
    assert validate_release_manifest(MANIFEST) == []


def test_validate_release_manifest_rejects_placeholder_commits() -> None:
    manifest = json.loads(INVALID_PLACEHOLDER.read_text())
    issues = validate_release_manifest(INVALID_PLACEHOLDER)
    assert issues
    assert any("placeholder" in err for err in issues)
    assert manifest["labtrust_gym_commit"] == "a" * 40


def test_validate_release_manifest_rejects_certifyedge_commit_mismatch() -> None:
    issues = validate_release_manifest(INVALID_CE)
    assert issues
    assert any("certifyedge" in err.lower() for err in issues)


def test_validate_release_manifest_rejects_pf_commit_mismatch() -> None:
    issues = validate_release_manifest(INVALID_PF)
    assert issues
    assert any("provability" in err.lower() or "verification" in err.lower() for err in issues)


def test_validate_release_manifest_rejects_labtrust_commit_mismatch() -> None:
    issues = validate_release_manifest(INVALID_LT)
    assert issues
    assert any("labtrust" in err.lower() for err in issues)


def test_validate_release_manifest_rejects_hash_mismatch() -> None:
    base = json.loads(MANIFEST.read_text())
    bad = copy.deepcopy(base)
    first = MANIFEST_ARTIFACTS[0]
    bad["artifacts"][first] = "sha256:" + "f" * 64
    path = release_dir() / "_tmp_invalid_hash_manifest.json"
    try:
        path.write_text(json.dumps(bad, indent=2) + "\n", encoding="utf-8")
        issues = validate_release_manifest(path)
        assert issues
        assert any("digest mismatch" in err for err in issues)
    finally:
        if path.exists():
            path.unlink()
