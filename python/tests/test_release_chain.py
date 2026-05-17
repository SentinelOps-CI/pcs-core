"""PCS v0.1 atomic LabTrust release-chain validation."""

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
from pcs_core.release_fixtures import (
    MANIFEST_ARTIFACTS,
    release_dir,
    validate_release_manifest,
)

MANIFEST = release_dir() / "RELEASE_FIXTURE_MANIFEST.json"
INVALID_MIXED = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "labtrust-release-invalid"
    / "mixed_certificate_id"
)
INVALID_PLACEHOLDER = release_dir() / "invalid_placeholder_commit_manifest.json"
INVALID_CE = release_dir() / "invalid_mismatched_certifyedge_commit_manifest.json"
INVALID_PF = release_dir() / "invalid_mismatched_pf_commit_manifest.json"
INVALID_LT = release_dir() / "invalid_mismatched_labtrust_commit_manifest.json"


def _codes(path: Path) -> set[str]:
    return {issue.code for issue in validate_release_chain(path)}


def test_resolve_release_chain_directory_from_python_relative_path() -> None:
    assert resolve_release_chain_directory(Path("examples/labtrust-release")) == release_dir()


def test_validate_release_manifest_passes_on_current_fixture() -> None:
    assert validate_release_manifest(MANIFEST) == []
    assert validate_release_chain(release_dir()) == []


def test_validate_release_chain_passes_on_current_fixture() -> None:
    assert validate_release_chain(release_dir()) == []


def test_canonical_rc_pin_values_in_manifest_and_artifacts() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["labtrust_gym_commit"] == LABTRUST_RC_LABTRUST_GYM_COMMIT
    assert manifest["certifyedge_commit"] == LABTRUST_RC_CERTIFYEDGE_COMMIT
    assert manifest["provability_fabric_commit"] == LABTRUST_RC_PROVABILITY_FABRIC_COMMIT
    assert manifest["scientific_memory_commit"] == LABTRUST_RC_SCIENTIFIC_MEMORY_COMMIT
    assert (
        manifest["artifacts"]["science_claim_bundle.certified.json"]
        == LABTRUST_RC_CERTIFIED_BUNDLE_HASH
    )

    trace_cert = json.loads((release_dir() / "trace_certificate.json").read_text())
    assert trace_cert["certificate_id"] == LABTRUST_RC_CERTIFICATE_ID
    assert trace_cert["trace_hash"] == LABTRUST_RC_TRACE_HASH

    trace = json.loads((release_dir() / "trace.json").read_text())
    assert trace["trace_hash"] == LABTRUST_RC_TRACE_HASH


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


@pytest.mark.skipif(not INVALID_MIXED.is_dir(), reason="mixed_certificate_id fixture not present")
def test_validate_release_chain_rejects_mixed_certificate_id_fixture() -> None:
    issues = validate_release_chain(INVALID_MIXED)
    codes = {issue.code for issue in issues}
    assert "mixed_certificate_id" in codes
