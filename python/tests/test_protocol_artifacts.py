"""PCS Phase 2 protocol artifact schemas and semantics."""

import json
from pathlib import Path

import pytest

from pcs_core.hash import canonical_hash
from pcs_core.protocol_fixtures import (
    LABTRUST_PROTOCOL_ARTIFACTS,
    handoff_manifest_valid,
    release_chain_validation_result_valid,
    release_manifest_valid,
)
from pcs_core.validate import ValidationError, validate_file

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_release_manifest_valid_example() -> None:
    assert validate_file(EXAMPLES / "release_manifest.valid.json") == "ReleaseManifest.v0"


def test_handoff_manifest_valid_example() -> None:
    assert validate_file(EXAMPLES / "handoff_manifest.valid.json") == "HandoffManifest.v0"


def test_release_chain_validation_result_valid_example() -> None:
    path = EXAMPLES / "release_chain_validation_result.valid.json"
    assert validate_file(path) == "ReleaseChainValidationResult.v0"


def test_protocol_fixtures_match_on_disk_examples() -> None:
    on_disk = json.loads((EXAMPLES / "release_manifest.valid.json").read_text(encoding="utf-8"))
    built = release_manifest_valid()
    assert on_disk["release_id"] == built["release_id"]
    assert on_disk["artifacts"] == built["artifacts"]
    assert on_disk["producer_repos"] == built["producer_repos"]
    assert on_disk["chain_root"] == built["chain_root"]
    assert on_disk["canonical_claim_id"] == built["canonical_claim_id"]


def test_invalid_release_manifest_placeholder_commit_fails() -> None:
    with pytest.raises(ValidationError):
        validate_file(EXAMPLES / "invalid_release_manifest_placeholder_commit.json")


def test_invalid_handoff_manifest_missing_input_hash_fails() -> None:
    with pytest.raises(ValidationError):
        validate_file(EXAMPLES / "invalid_handoff_manifest_missing_input_hash.json")


def test_invalid_release_chain_validation_failed_status_fails() -> None:
    with pytest.raises(ValidationError):
        validate_file(EXAMPLES / "invalid_release_chain_validation_failed_status.json")


def test_release_manifest_canonical_hash_stable() -> None:
    doc = release_manifest_valid()
    assert doc["signature_or_digest"] == canonical_hash(
        {k: v for k, v in doc.items() if k != "signature_or_digest"},
    )


def test_handoff_manifest_builder() -> None:
    doc = handoff_manifest_valid()
    assert doc["handoff_kind"] == "bundle_to_verifier"
    assert doc["invariants"]["certificate_id"].startswith("cert-trace-")


def test_labtrust_protocol_artifact_map_complete() -> None:
    assert len(LABTRUST_PROTOCOL_ARTIFACTS) == 6


def test_release_chain_validation_result_builder() -> None:
    doc = release_chain_validation_result_valid()
    assert doc["status"] == "ProofChecked"
    assert doc["artifacts_checked"] == 8
