"""PR13: canonical_hash_legacy vs canonical_hash_release parity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.hash import (
    CANONICALIZATION_VERSION,
    REJECTION_FLOAT_PROHIBITED,
    REJECTION_INTEGER_OUT_OF_RANGE,
    REJECTION_NEGATIVE_ZERO,
    SAFE_INTEGER_MAX,
    SAFE_INTEGER_MIN,
    CanonicalizationError,
    canonical_hash,
    canonical_hash_legacy,
    canonical_hash_release,
    canonical_json_bytes,
    try_canonical_hash_release,
)

REPO = Path(__file__).resolve().parents[2]
CANON_V1 = REPO / "test_vectors" / "hash" / "canonical_json_v1"


def test_legacy_aliases_canonical_hash() -> None:
    payload = {"schema_version": "v0", "artifact_type": "CanonicalProbe.v0", "n": 1}
    assert canonical_hash_legacy(payload) == canonical_hash(payload)


def test_release_matches_legacy_on_safe_payloads() -> None:
    payload = {
        "schema_version": "v0",
        "artifact_type": "CanonicalProbe.v0",
        "lo": SAFE_INTEGER_MIN,
        "hi": SAFE_INTEGER_MAX,
    }
    assert canonical_hash_release(payload) == canonical_hash_legacy(payload)


def test_release_rejects_with_normalized_codes() -> None:
    with pytest.raises(CanonicalizationError) as float_exc:
        canonical_hash_release({"x": 1.5})
    assert float_exc.value.code == REJECTION_FLOAT_PROHIBITED

    with pytest.raises(CanonicalizationError) as hi_exc:
        canonical_hash_release({"x": SAFE_INTEGER_MAX + 1})
    assert hi_exc.value.code == REJECTION_INTEGER_OUT_OF_RANGE

    with pytest.raises(CanonicalizationError) as lo_exc:
        canonical_hash_release({"x": SAFE_INTEGER_MIN - 1})
    assert lo_exc.value.code == REJECTION_INTEGER_OUT_OF_RANGE

    with pytest.raises(CanonicalizationError) as neg_exc:
        canonical_hash_release({"x": -0.0})
    assert neg_exc.value.code == REJECTION_NEGATIVE_ZERO


def test_try_canonical_hash_release_result() -> None:
    digest, code = try_canonical_hash_release({"ok": True})
    assert digest is not None and code is None
    digest, code = try_canonical_hash_release({"x": 1.5})
    assert digest is None and code == REJECTION_FLOAT_PROHIBITED


def test_canonical_json_v1_accept_vectors() -> None:
    vectors = json.loads((CANON_V1 / "vectors.json").read_text(encoding="utf-8"))
    assert vectors["canonicalization_version"] == CANONICALIZATION_VERSION
    for case in vectors["cases"]:
        case_id = case["case_id"]
        payload = json.loads((CANON_V1 / case_id / "input.json").read_text(encoding="utf-8"))
        assert canonical_json_bytes(payload).decode("utf-8") == case["canonical_json"]
        digest = canonical_hash_legacy(payload)
        assert digest == case["expected_digest"]
        assert canonical_hash_release(payload) == digest
        assert (CANON_V1 / case_id / "digest.txt").read_text(encoding="utf-8").strip() == digest


def test_canonical_json_v1_release_reject_vectors() -> None:
    vectors = json.loads((CANON_V1 / "vectors.json").read_text(encoding="utf-8"))
    for case in vectors["release_reject_cases"]:
        case_id = case["case_id"]
        payload = json.loads((CANON_V1 / case_id / "input.json").read_text(encoding="utf-8"))
        digest, code = try_canonical_hash_release(payload)
        assert digest is None
        assert code == case["expected_rejection"]
        assert (
            CANON_V1 / case_id / "expected_rejection.txt"
        ).read_text(encoding="utf-8").strip() == case["expected_rejection"]
        legacy = canonical_hash_legacy(payload)
        assert legacy == case["legacy_digest"]
        assert (CANON_V1 / case_id / "legacy_digest.txt").read_text(encoding="utf-8").strip() == legacy
