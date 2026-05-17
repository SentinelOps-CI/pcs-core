import json
from pathlib import Path

import pytest

from pcs_core.validate import ValidationError, validate_artifact, validate_semantics

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_certified_bundle_requires_certificate() -> None:
    data = json.loads(
        (EXAMPLES / "science_claim_bundle.certified.valid.json").read_text(encoding="utf-8")
    )
    data["certificates"] = []
    with pytest.raises(ValidationError) as exc:
        validate_artifact(data, "ScienceClaimBundle.v0")
    assert any("TraceCertificate" in e for e in exc.value.errors)


def test_pending_bundle_allows_empty_certificates() -> None:
    data = json.loads(
        (EXAMPLES / "science_claim_bundle.pending.valid.json").read_text(encoding="utf-8")
    )
    validate_artifact(data, "ScienceClaimBundle.v0")


def test_trace_hash_mismatch_semantic_only() -> None:
    data = json.loads(
        (EXAMPLES / "science_claim_bundle.certified.valid.json").read_text(encoding="utf-8")
    )
    data["certificates"][0]["trace_hash"] = "sha256:" + "e" * 64
    errors = validate_semantics(data, "ScienceClaimBundle.v0")
    assert any("trace_hash mismatch" in e for e in errors)


def test_zero_commit_with_local_dev_allowed() -> None:
    data = json.loads(
        (EXAMPLES / "invalid_zero_source_commit.release.json").read_text(encoding="utf-8")
    )
    data["local_dev"] = True
    validate_artifact(data, "RuntimeReceipt.v0")
