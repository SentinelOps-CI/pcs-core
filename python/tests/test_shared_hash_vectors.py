"""Cross-language shared hash vectors under test_vectors/hash/."""

import json
from pathlib import Path

import pytest

from pcs_core.hash import SIGNATURE_FIELD, canonical_hash, canonical_json_bytes
from pcs_core.shared_hash_vectors import (
    VECTOR_SPECS,
    verify_shared_vectors,
    write_shared_vectors,
)

REPO = Path(__file__).resolve().parents[2]
VECTORS = REPO / "test_vectors" / "hash"
EXAMPLES = REPO / "examples"


@pytest.fixture(scope="module", autouse=True)
def ensure_vectors_exist() -> None:
    if not any(VECTORS.glob("*.vector.json")):
        write_shared_vectors(force=True)


def test_verify_shared_vectors_clean() -> None:
    assert verify_shared_vectors() == []


@pytest.mark.parametrize("artifact_type", list(VECTOR_SPECS))
def test_hash_ignores_signature_or_digest(artifact_type: str) -> None:
    example_name = VECTOR_SPECS[artifact_type]
    data = json.loads((EXAMPLES / example_name).read_text(encoding="utf-8"))
    base = canonical_hash(data)
    if SIGNATURE_FIELD in data:
        mutated = dict(data)
        mutated[SIGNATURE_FIELD] = "sha256:" + "f" * 64
        assert canonical_hash(mutated) == base


def test_shared_vector_files_match_examples(artifact_type: str = "RuntimeReceipt.v0") -> None:
    slug = artifact_type.replace(".v0", "").replace(".", "_").lower()
    vector = json.loads((VECTORS / f"{slug}.vector.json").read_text(encoding="utf-8"))
    example_name = vector["input_file"]
    data = json.loads((EXAMPLES / example_name).read_text(encoding="utf-8"))
    assert canonical_hash(data) == vector["expected_digest"]
    assert canonical_json_bytes(data).decode("utf-8") == vector["canonical_json"]
