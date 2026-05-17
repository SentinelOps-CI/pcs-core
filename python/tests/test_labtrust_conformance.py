"""Cross-repo LabTrust flow fixtures under examples/labtrust/."""

import json
from pathlib import Path

import pytest

from pcs_core.hash import canonical_hash, canonical_json_bytes
from pcs_core.validate import ValidationError, validate_file

LABTRUST = Path(__file__).resolve().parents[2] / "examples" / "labtrust"
VECTORS = Path(__file__).resolve().parent / "hash_vectors"

LABTRUST_SEQUENCE = [
    "science_claim_bundle.pending.valid.json",
    "trace_certificate.valid.json",
    "science_claim_bundle.certified.valid.json",
    "verification_result.valid.json",
    "signed_science_claim_bundle.valid.json",
]


def test_signed_science_claim_bundle_schema_version_is_v0() -> None:
    data = json.loads(
        (LABTRUST / "signed_science_claim_bundle.valid.json").read_text(encoding="utf-8"),
    )
    assert data["schema_version"] == "v0"


def test_invalid_signed_schema_version_artifact_name_fails() -> None:
    with pytest.raises(ValidationError):
        validate_file(LABTRUST / "invalid_signed_schema_version_artifact_name.json")


def test_invalid_singular_runtime_receipt_bundle_fails() -> None:
    with pytest.raises(ValidationError):
        validate_file(LABTRUST / "invalid_singular_runtime_receipt_bundle.json")


def test_labtrust_fixture_sequence_validates() -> None:
    for filename in LABTRUST_SEQUENCE:
        artifact_type = validate_file(LABTRUST / filename)
        assert artifact_type


def test_hash_vectors_cover_signed_bundle() -> None:
    artifact = "SignedScienceClaimBundle.v0"
    vector_dir = VECTORS / artifact
    data = json.loads((vector_dir / "input.json").read_text(encoding="utf-8"))
    expected_canonical = (vector_dir / "canonical.txt").read_text(encoding="utf-8").strip()
    expected_digest = (vector_dir / "digest.txt").read_text(encoding="utf-8").strip()
    assert data["schema_version"] == "v0"
    assert bytes(canonical_json_bytes(data)).decode("utf-8") == expected_canonical
    assert canonical_hash(data) == expected_digest
