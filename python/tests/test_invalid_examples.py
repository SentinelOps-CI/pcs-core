from pathlib import Path

import pytest

from pcs_core.validate import ValidationError, validate_artifact, validate_file

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_unknown_status_rejected() -> None:
    import json

    data = json.loads((EXAMPLES / "invalid_unknown_status.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        validate_artifact(data, "RuntimeReceipt.v0")


def test_missing_assumption_set_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_file(EXAMPLES / "invalid_missing_assumption_set.json")


def test_mismatched_trace_hash_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_file(EXAMPLES / "invalid_mismatched_trace_hash.json")


def test_zero_source_commit_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_file(EXAMPLES / "invalid_zero_source_commit.release.json")


def test_labtrust_legacy_singular_receipt_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_file(EXAMPLES / "labtrust/invalid_pf_legacy_singular_receipt.json")


def test_labtrust_signed_schema_version_artifact_name_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_file(EXAMPLES / "labtrust/invalid_signed_schema_version_artifact_name.json")
