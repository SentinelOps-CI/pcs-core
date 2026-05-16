from pathlib import Path

import pytest

from pcs_core.validate import validate_file

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.mark.parametrize(
    "filename",
    [
        "assumption_set.valid.json",
        "source_span.valid.json",
        "claim_artifact.valid.json",
        "runtime_receipt.valid.json",
        "trace_certificate.valid.json",
        "evidence_bundle.valid.json",
        "science_claim_bundle.valid.json",
        "verification_result.valid.json",
    ],
)
def test_valid_examples(filename: str) -> None:
    artifact_type = validate_file(EXAMPLES / filename)
    assert artifact_type
