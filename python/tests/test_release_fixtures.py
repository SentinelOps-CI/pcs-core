"""PCS v0.1 LabTrust release fixture manifest helpers."""

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


def test_release_manifest_lists_all_artifacts() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(manifest["artifacts"]) == set(MANIFEST_ARTIFACTS)


def test_release_manifest_records_all_repo_commits() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for key in COMMIT_KEYS:
        commit = manifest[key]
        assert isinstance(commit, str)
        assert len(commit) == 40
        assert not is_placeholder_commit(commit), f"{key} must not be a placeholder"


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
