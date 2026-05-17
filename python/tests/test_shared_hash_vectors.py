"""Cross-language shared hash vectors under test_vectors/hash/."""

import json
from pathlib import Path

import pytest

from pcs_core.hash import SIGNATURE_FIELD, canonical_hash, canonical_json_bytes
from pcs_core.shared_hash_vectors import (
    VECTOR_FILENAMES,
    VECTOR_SPECS,
    vector_path,
    verify_shared_vectors,
    write_shared_vectors,
)

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module", autouse=True)
def ensure_vectors_exist() -> None:
    if not any((REPO / "test_vectors" / "hash").glob("*.vector.json")):
        write_shared_vectors(force=True)


def test_verify_shared_vectors_clean() -> None:
    assert verify_shared_vectors() == []


@pytest.mark.parametrize("artifact_type", list(VECTOR_SPECS))
def test_hash_ignores_signature_or_digest(artifact_type: str) -> None:
    relative = VECTOR_SPECS[artifact_type]
    data = json.loads((REPO / relative).read_text(encoding="utf-8"))
    base = canonical_hash(data)
    if SIGNATURE_FIELD in data:
        mutated = dict(data)
        mutated[SIGNATURE_FIELD] = "sha256:" + "f" * 64
        assert canonical_hash(mutated) == base


@pytest.mark.parametrize("artifact_type", list(VECTOR_SPECS))
def test_shared_vector_files_match_examples(artifact_type: str) -> None:
    vector = json.loads(vector_path(artifact_type).read_text(encoding="utf-8"))
    relative = str(vector.get("input", VECTOR_SPECS[artifact_type]))
    data = json.loads((REPO / relative).read_text(encoding="utf-8"))
    assert canonical_hash(data) == vector["expected_digest"]
    assert canonical_json_bytes(data).decode("utf-8") == vector["canonical_json"]


def test_hash_vector_filenames_catalog() -> None:
    for filename in VECTOR_FILENAMES.values():
        assert (REPO / "test_vectors" / "hash" / filename).is_file()
