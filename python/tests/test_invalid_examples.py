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
