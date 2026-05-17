"""PCS v0.1 LabTrust release fixture bundle."""

import copy
import json
from pathlib import Path

import pytest

from pcs_core.release_fixtures import (
    COMMIT_KEYS,
    MANIFEST_ARTIFACTS,
    RELEASE_PCS_ARTIFACTS,
    is_placeholder_commit,
    release_dir,
    validate_release_manifest,
)
from pcs_core.validate import validate_file

MANIFEST = release_dir() / "RELEASE_FIXTURE_MANIFEST.json"
INVALID_PLACEHOLDER = release_dir() / "invalid_placeholder_commit_manifest.json"
INVALID_CE_MISMATCH = release_dir() / "invalid_mismatched_certifyedge_commit_manifest.json"
INVALID_PF_MISMATCH = release_dir() / "invalid_mismatched_pf_commit_manifest.json"
INVALID_LT_MISMATCH = release_dir() / "invalid_mismatched_labtrust_commit_manifest.json"


@pytest.fixture(scope="module", autouse=True)
def _require_invalid_manifest_files() -> None:
    for path in (
        INVALID_PLACEHOLDER,
        INVALID_CE_MISMATCH,
        INVALID_PF_MISMATCH,
        INVALID_LT_MISMATCH,
    ):
        if not path.is_file():
            pytest.skip(f"missing invalid manifest fixture: {path.name}")


def _load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _write_invalid_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_validate_release_manifest_passes_on_current_fixture() -> None:
    assert validate_release_manifest(MANIFEST) == []


def test_validate_release_manifest_rejects_placeholder_commits() -> None:
    errors = validate_release_manifest(INVALID_PLACEHOLDER)
    assert errors
    joined = "\n".join(errors)
    assert "placeholder" in joined.lower()


def test_validate_release_manifest_rejects_certifyedge_commit_mismatch() -> None:
    errors = validate_release_manifest(INVALID_CE_MISMATCH)
    assert errors
    joined = "\n".join(errors)
    assert "certifyedge" in joined.lower() or "certified.certificates" in joined


def test_validate_release_manifest_rejects_pf_commit_mismatch() -> None:
    errors = validate_release_manifest(INVALID_PF_MISMATCH)
    assert errors
    joined = "\n".join(errors)
    assert "provability" in joined.lower() or "verification_result" in joined


def test_validate_release_manifest_rejects_labtrust_commit_mismatch() -> None:
    errors = validate_release_manifest(INVALID_LT_MISMATCH)
    assert errors
    joined = "\n".join(errors)
    assert "labtrust" in joined.lower() or "runtime_receipt" in joined


def test_validate_release_manifest_rejects_hash_mismatch() -> None:
    base = _load_manifest()
    bad = copy.deepcopy(base)
    first = MANIFEST_ARTIFACTS[0]
    bad["artifacts"][first] = "sha256:" + "f" * 64
    path = release_dir() / "_tmp_invalid_hash_manifest.json"
    try:
        _write_invalid_manifest(path, bad)
        errors = validate_release_manifest(path)
        assert errors
        assert any("digest mismatch" in err for err in errors)
    finally:
        if path.exists():
            path.unlink()


def test_release_manifest_lists_all_artifacts() -> None:
    manifest = _load_manifest()
    assert set(manifest["artifacts"]) == set(MANIFEST_ARTIFACTS)


def test_release_manifest_records_all_repo_commits() -> None:
    manifest = _load_manifest()
    for key in COMMIT_KEYS:
        commit = manifest[key]
        assert isinstance(commit, str)
        assert len(commit) == 40
        assert not is_placeholder_commit(commit), f"{key} must not be a placeholder"


@pytest.mark.parametrize("commit", [
    "a" * 40,
    "b" * 40,
    "c" * 40,
    "d" * 40,
    "e" * 40,
    "0" * 40,
])
def test_is_placeholder_commit_detects_patterns(commit: str) -> None:
    assert is_placeholder_commit(commit)


def test_is_placeholder_commit_allows_real_hashes() -> None:
    assert not is_placeholder_commit("f4e895b65e401d6936573276f913e079c8f7cd0b")


@pytest.mark.parametrize("filename", RELEASE_PCS_ARTIFACTS)
def test_release_pcs_artifacts_validate(filename: str) -> None:
    validate_file(release_dir() / filename)


def test_regenerate_release_fixtures_from_chain() -> None:
    import os

    work = os.environ.get("PCS_CHAIN_WORK", "").strip()
    if not work:
        pytest.skip("PCS_CHAIN_WORK not set (run clean-checkout chain to test regeneration)")

    from pcs_core.release_fixtures import write_release_fixtures

    path = write_release_fixtures(workdir=Path(work))
    assert (path / "RELEASE_FIXTURE_MANIFEST.json").is_file()
    assert validate_release_manifest(path / "RELEASE_FIXTURE_MANIFEST.json") == []

