import json
from pathlib import Path

import pytest

from pcs_core.hash import canonical_hash, canonical_json_bytes

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
VECTORS = Path(__file__).resolve().parent / "hash_vectors"


def test_canonical_hash_stable() -> None:
    path = EXAMPLES / "science_claim_bundle.certified.valid.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert canonical_hash(data) == canonical_hash(data)
    assert canonical_hash(data).startswith("sha256:")


def test_signature_excluded_from_hash() -> None:
    path = EXAMPLES / "runtime_receipt.valid.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    base = canonical_hash(data)
    mutated = dict(data)
    mutated["signature_or_digest"] = "sha256:" + "0" * 64
    assert canonical_hash(mutated) == base


@pytest.mark.parametrize(
    "artifact",
    [
        "RuntimeReceipt.v0",
        "TraceCertificate.v0",
        "ScienceClaimBundle.v0",
        "SignedScienceClaimBundle.v0",
    ],
)
def test_hash_vectors(artifact: str) -> None:
    vector_dir = VECTORS / artifact
    input_path = vector_dir / "input.json"
    canonical_path = vector_dir / "canonical.txt"
    digest_path = vector_dir / "digest.txt"
    assert input_path.is_file(), f"missing {input_path}"
    data = json.loads(input_path.read_text(encoding="utf-8"))
    expected_canonical = canonical_path.read_text(encoding="utf-8").strip()
    expected_digest = digest_path.read_text(encoding="utf-8").strip()
    assert bytes(canonical_json_bytes(data)).decode("utf-8") == expected_canonical
    assert canonical_hash(data) == expected_digest
