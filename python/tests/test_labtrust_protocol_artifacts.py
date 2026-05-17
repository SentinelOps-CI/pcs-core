"""Phase 2 protocol artifacts in examples/labtrust-release/ (must be committed on disk)."""

import json
from pathlib import Path

import pytest

from pcs_core.protocol_fixtures import (
    LABTRUST_PROTOCOL_ARTIFACTS,
    labtrust_release_manifest_body,
    release_manifest_valid,
)
from pcs_core.validate import validate_file

RELEASE = Path(__file__).resolve().parents[2] / "examples" / "labtrust-release"


@pytest.fixture(scope="module", autouse=True)
def require_committed_protocol_artifacts() -> None:
    missing = [name for name in LABTRUST_PROTOCOL_ARTIFACTS if not (RELEASE / name).is_file()]
    if missing:
        pytest.fail(
            f"Missing committed protocol artifacts under {RELEASE}: {missing}. "
            "Run: just materialize-labtrust-protocol",
        )


@pytest.mark.parametrize("filename", list(LABTRUST_PROTOCOL_ARTIFACTS))
def test_protocol_artifact_validates(filename: str) -> None:
    path = RELEASE / filename
    validate_file(path)


def test_release_manifest_hashes_match_legacy_manifest() -> None:
    legacy = json.loads((RELEASE / "RELEASE_FIXTURE_MANIFEST.json").read_text(encoding="utf-8"))
    manifest = json.loads((RELEASE / "release_manifest.v0.json").read_text(encoding="utf-8"))
    legacy_hashes = legacy["artifacts"]
    for name, entry in manifest["artifacts"].items():
        assert entry["sha256"] == legacy_hashes[name], name


def test_release_manifest_body_matches_builder() -> None:
    on_disk = json.loads((RELEASE / "release_manifest.v0.json").read_text(encoding="utf-8"))
    built = release_manifest_valid()
    assert on_disk["release_id"] == built["release_id"]
    assert on_disk["artifacts"] == built["artifacts"]
    assert on_disk["producer_repos"] == built["producer_repos"]
    body = labtrust_release_manifest_body()
    assert on_disk["release_candidate"] == body["release_candidate"]
