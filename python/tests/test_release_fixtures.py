"""PCS v0.1 LabTrust release fixture bundle."""

import json

import pytest

from pcs_core.release_fixtures import (
    MANIFEST_ARTIFACTS,
    RELEASE_PCS_ARTIFACTS,
    release_dir,
    verify_release_fixtures,
    write_release_fixtures,
)
from pcs_core.validate import validate_file


def test_release_manifest_lists_all_artifacts() -> None:
    manifest = json.loads((release_dir() / "RELEASE_FIXTURE_MANIFEST.json").read_text())
    assert set(manifest["artifacts"]) == set(MANIFEST_ARTIFACTS)


def test_release_manifest_records_all_repo_commits() -> None:
    manifest = json.loads((release_dir() / "RELEASE_FIXTURE_MANIFEST.json").read_text())
    for key in (
        "pcs_core_commit",
        "labtrust_gym_commit",
        "certifyedge_commit",
        "provability_fabric_commit",
        "scientific_memory_commit",
    ):
        assert isinstance(manifest[key], str)
        assert len(manifest[key]) >= 40


@pytest.mark.parametrize("filename", RELEASE_PCS_ARTIFACTS)
def test_release_pcs_artifacts_validate(filename: str) -> None:
    validate_file(release_dir() / filename)


def test_verify_release_fixtures_passes() -> None:
    assert verify_release_fixtures() == []


def test_regenerate_release_fixtures() -> None:
    path = write_release_fixtures()
    assert (path / "RELEASE_FIXTURE_MANIFEST.json").is_file()
    assert verify_release_fixtures() == []
