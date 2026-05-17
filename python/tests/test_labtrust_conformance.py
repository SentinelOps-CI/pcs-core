"""Cross-repo LabTrust flow fixtures under examples/labtrust/."""

from pathlib import Path

import pytest

from pcs_core.validate import ValidationError, validate_file

LABTRUST = Path(__file__).resolve().parents[2] / "examples" / "labtrust"

VALID_FIXTURES = [
    "science_claim_bundle.pending.valid.json",
    "trace_certificate.valid.json",
    "science_claim_bundle.certified.valid.json",
    "verification_result.valid.json",
    "signed_science_claim_bundle.valid.json",
]

INVALID_FIXTURES = [
    "invalid_pf_legacy_singular_receipt.json",
    "invalid_signed_schema_version_artifact_name.json",
]


@pytest.mark.parametrize("filename", VALID_FIXTURES)
def test_labtrust_valid_fixtures(filename: str) -> None:
    path = LABTRUST / filename
    artifact_type = validate_file(path)
    assert artifact_type


@pytest.mark.parametrize("filename", INVALID_FIXTURES)
def test_labtrust_invalid_fixtures_rejected(filename: str) -> None:
    with pytest.raises(ValidationError):
        validate_file(LABTRUST / filename)


def test_signed_bundle_uses_protocol_schema_version() -> None:
    import json

    data = json.loads(
        (LABTRUST / "signed_science_claim_bundle.valid.json").read_text(encoding="utf-8"),
    )
    assert data["schema_version"] == "v0"
