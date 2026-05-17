"""PCS protocol hardening conformance tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from pcs_core.legacy_manifest import legacy_manifest_equivalent_to_release_manifest
from pcs_core.migrate import migrate_file
from pcs_core.paths import examples_dir
from pcs_core.protocol_fixtures import release_manifest_valid
from pcs_core.registry import (
    build_artifact_registry,
    check_artifact_against_registry,
    registry_entries,
)
from pcs_core.release_chain_report import build_release_chain_validation_result
from pcs_core.release_fixtures import release_dir
from pcs_core.shared_hash_vectors import VECTOR_FILENAMES, verify_shared_vectors
from pcs_core.status_policy import check_status_transition
from pcs_core.validate import ValidationError, validate_artifact, validate_file

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "examples" / "labtrust-release"
LEGACY_MANIFEST = RELEASE / "RELEASE_FIXTURE_MANIFEST.json"
RELEASE_MANIFEST_V0 = RELEASE / "release_manifest.v0.json"


def test_release_manifest_v0_validates() -> None:
    assert validate_file(RELEASE_MANIFEST_V0) == "ReleaseManifest.v0"


def test_release_manifest_legacy_equivalence() -> None:
    legacy = json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))
    release = json.loads(RELEASE_MANIFEST_V0.read_text(encoding="utf-8"))
    drift = legacy_manifest_equivalent_to_release_manifest(legacy, release)
    assert drift == [], drift


def test_validate_release_chain_emits_release_chain_validation_result() -> None:
    result = build_release_chain_validation_result(release_dir())
    assert result["status"] == "ProofChecked"
    assert len(result["checks"]) == 30
    validate_artifact(result, "ReleaseChainValidationResult.v0")


def test_artifact_registry_contains_all_v0_artifacts() -> None:
    expected = set(registry_entries().keys())
    on_disk = build_artifact_registry()["entries"]
    assert expected == set(on_disk.keys())


def test_registry_check_artifact_fails_wrong_producer(tmp_path: Path) -> None:
    path = release_dir() / "trace_certificate.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = copy.deepcopy(data)
    bad["producer"] = "LabTrust-Gym"
    bad_path = tmp_path / "bad_trace_certificate.json"
    bad_path.write_text(json.dumps(bad, indent=2) + "\n", encoding="utf-8")
    errors = check_artifact_against_registry(bad_path)
    assert any("producer" in err for err in errors)


def test_registry_check_artifact_fails_disallowed_status(tmp_path: Path) -> None:
    path = release_dir() / "trace_certificate.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = copy.deepcopy(data)
    bad["status"] = "Draft"
    bad_path = tmp_path / "bad_status.json"
    bad_path.write_text(json.dumps(bad, indent=2) + "\n", encoding="utf-8")
    errors = check_artifact_against_registry(bad_path)
    assert any("allowed_statuses" in err for err in errors)


def test_python_shared_hash_vectors_verify() -> None:
    assert verify_shared_vectors() == []


def test_hash_vector_files_use_canonical_names() -> None:
    for filename in VECTOR_FILENAMES.values():
        assert (ROOT / "test_vectors" / "hash" / filename).is_file()


def test_migration_report_validates() -> None:
    path = examples_dir() / "migration_report.valid.json"
    assert validate_file(path) == "MigrationReport.v0"


def test_migrate_emits_valid_report(tmp_path: Path) -> None:
    src = examples_dir() / "runtime_receipt.valid.json"
    dest = tmp_path / "runtime_receipt.json"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    report = migrate_file(dest, from_version="v0", to_version="v0")
    validate_artifact(report, "MigrationReport.v0")
    assert report["status"] == "noop"


@pytest.mark.parametrize(
    ("old_status", "new_status"),
    [
        ("Rejected", "ProofChecked"),
        ("Stale", "ProofChecked"),
        ("RuntimeObserved", "ProofChecked"),
    ],
)
def test_status_transition_forbidden_cases(old_status: str, new_status: str) -> None:
    verdict = check_status_transition(old_status, new_status)
    assert not verdict.allowed


def test_built_release_manifest_matches_fixture_builder() -> None:
    built = release_manifest_valid()
    on_disk = json.loads(RELEASE_MANIFEST_V0.read_text(encoding="utf-8"))
    assert on_disk["chain_root"] == built["chain_root"]
