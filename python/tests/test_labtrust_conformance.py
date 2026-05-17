"""Frozen LabTrust v0.1 conformance fixtures under examples/labtrust/."""

import json
from pathlib import Path

import pytest

from pcs_core.hash import canonical_hash, canonical_json_bytes
from pcs_core.validate import ValidationError, validate_file

LABTRUST = Path(__file__).resolve().parents[2] / "examples" / "labtrust"
VECTORS = Path(__file__).resolve().parent / "hash_vectors"


def test_labtrust_pending_bundle_validates() -> None:
    assert validate_file(LABTRUST / "science_claim_bundle.pending.valid.json")


def test_labtrust_trace_certificate_validates() -> None:
    assert validate_file(LABTRUST / "trace_certificate.valid.json")


def test_labtrust_certified_bundle_validates() -> None:
    assert validate_file(LABTRUST / "science_claim_bundle.certified.valid.json")


def test_labtrust_verification_result_validates() -> None:
    assert validate_file(LABTRUST / "verification_result.valid.json")


def test_labtrust_signed_bundle_validates() -> None:
    artifact_type = validate_file(LABTRUST / "signed_science_claim_bundle.valid.json")
    assert artifact_type == "SignedScienceClaimBundle.v0"
    data = json.loads(
        (LABTRUST / "signed_science_claim_bundle.valid.json").read_text(encoding="utf-8"),
    )
    assert data["schema_version"] == "v0"


def test_invalid_singular_runtime_receipt_bundle_fails() -> None:
    with pytest.raises(ValidationError):
        validate_file(LABTRUST / "invalid_singular_runtime_receipt_bundle.json")


def test_invalid_signed_schema_version_artifact_name_fails() -> None:
    with pytest.raises(ValidationError):
        validate_file(LABTRUST / "invalid_signed_schema_version_artifact_name.json")


def test_invalid_failed_verification_result_fails_semantic_import_contract() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_file(LABTRUST / "invalid_failed_verification_result.json")
    assert any("import contract" in err.lower() for err in exc_info.value.errors)


def test_invalid_missing_trace_certificate_fails() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_file(LABTRUST / "invalid_missing_trace_certificate.json")
    assert any("TraceCertificate" in err for err in exc_info.value.errors)


def test_hash_vectors_cover_signed_bundle() -> None:
    artifact = "SignedScienceClaimBundle.v0"
    vector_dir = VECTORS / artifact
    data = json.loads((vector_dir / "input.json").read_text(encoding="utf-8"))
    expected_canonical = (vector_dir / "canonical.txt").read_text(encoding="utf-8").strip()
    expected_digest = (vector_dir / "digest.txt").read_text(encoding="utf-8").strip()
    assert data["schema_version"] == "v0"
    assert bytes(canonical_json_bytes(data)).decode("utf-8") == expected_canonical
    assert canonical_hash(data) == expected_digest
