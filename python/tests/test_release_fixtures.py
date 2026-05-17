"""PCS v0.1 LabTrust release fixture bundle."""

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
    verify_release_fixtures,
)
from pcs_core.validate import validate_file

INVALID_MANIFEST = release_dir() / "invalid_placeholder_commits_manifest.json"


def test_release_manifest_lists_all_artifacts() -> None:
    manifest = json.loads((release_dir() / "RELEASE_FIXTURE_MANIFEST.json").read_text())
    assert set(manifest["artifacts"]) == set(MANIFEST_ARTIFACTS)


def test_release_manifest_records_all_repo_commits() -> None:
    manifest = json.loads((release_dir() / "RELEASE_FIXTURE_MANIFEST.json").read_text())
    for key in COMMIT_KEYS:
        commit = manifest[key]
        assert isinstance(commit, str)
        assert len(commit) == 40
        assert not is_placeholder_commit(commit), f"{key} must not be a placeholder"


def test_release_manifest_rejects_placeholder_commits() -> None:
    errors = validate_release_manifest(INVALID_MANIFEST)
    assert errors, "placeholder manifest must fail validation"
    joined = "\n".join(errors)
    for key in (
        "pcs_core_commit",
        "labtrust_gym_commit",
        "certifyedge_commit",
        "provability_fabric_commit",
        "scientific_memory_commit",
    ):
        assert key in joined


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


def test_verify_release_fixtures_passes() -> None:
    assert verify_release_fixtures() == []


def test_validate_release_manifest_cli_path() -> None:
    manifest = release_dir() / "RELEASE_FIXTURE_MANIFEST.json"
    assert validate_release_manifest(manifest) == []


def test_regenerate_release_fixtures_from_chain() -> None:
    pytest.importorskip("os")
    import os

    work = os.environ.get("PCS_CHAIN_WORK", "").strip()
    if not work:
        pytest.skip("PCS_CHAIN_WORK not set (run clean-checkout chain to test regeneration)")

    from pcs_core.release_fixtures import write_release_fixtures

    path = write_release_fixtures(workdir=Path(work))
    assert (path / "RELEASE_FIXTURE_MANIFEST.json").is_file()
    assert verify_release_fixtures() == []
