import json
from pathlib import Path

from pcs_core.hash import canonical_hash

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_canonical_hash_stable() -> None:
    path = EXAMPLES / "science_claim_bundle.valid.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    h1 = canonical_hash(data)
    h2 = canonical_hash(data)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_signature_excluded_from_hash() -> None:
    path = EXAMPLES / "runtime_receipt.valid.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    base = canonical_hash(data)
    mutated = dict(data)
    mutated["signature_or_digest"] = "sha256:" + "0" * 64
    assert canonical_hash(mutated) == base
