"""Generate Canonical JSON v1 edge-case vectors (run from repo or python/)."""

from __future__ import annotations

import json
from pathlib import Path

from pcs_core.hash import CANONICALIZATION_VERSION, canonical_hash, canonical_json_bytes

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "test_vectors" / "hash" / "canonical_json_v1"

CASES: dict[str, dict] = {
    "unicode": {
        "schema_version": "v0",
        "artifact_type": "CanonicalProbe.v0",
        "text": "café",
    },
    "escaped_characters": {
        "schema_version": "v0",
        "artifact_type": "CanonicalProbe.v0",
        "text": "line1\nline2\t\"quoted\"",
    },
    "safe_integer_boundaries": {
        "schema_version": "v0",
        "artifact_type": "CanonicalProbe.v0",
        "lo": -9007199254740991,
        "hi": 9007199254740991,
    },
    "large_integers_as_strings": {
        "schema_version": "v0",
        "artifact_type": "CanonicalProbe.v0",
        "big": "9007199254740993",
    },
    "empty_object": {
        "schema_version": "v0",
        "artifact_type": "CanonicalProbe.v0",
        "empty": {},
    },
    "empty_array": {
        "schema_version": "v0",
        "artifact_type": "CanonicalProbe.v0",
        "empty": [],
    },
    "nested_key_ordering": {
        "schema_version": "v0",
        "artifact_type": "CanonicalProbe.v0",
        "z": 1,
        "a": {"c": 3, "b": 2},
        "m": 0,
    },
    "array_order_significant": {
        "schema_version": "v0",
        "artifact_type": "CanonicalProbe.v0",
        "events": [{"id": "b"}, {"id": "a"}],
    },
    "negative_zero_integer": {
        "schema_version": "v0",
        "artifact_type": "CanonicalProbe.v0",
        "value": 0,
    },
    "exponent_forms_as_strings": {
        "schema_version": "v0",
        "artifact_type": "CanonicalProbe.v0",
        "scientific": "1.23e+4",
    },
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict = {"canonicalization_version": CANONICALIZATION_VERSION, "cases": []}
    for name, payload in CASES.items():
        digest = canonical_hash(payload)
        canon = canonical_json_bytes(payload).decode("utf-8")
        case_dir = OUT / name
        case_dir.mkdir(exist_ok=True)
        (case_dir / "input.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (case_dir / "canonical.txt").write_text(canon + "\n", encoding="utf-8")
        (case_dir / "digest.txt").write_text(digest + "\n", encoding="utf-8")
        manifest["cases"].append(
            {
                "case_id": name,
                "expected_digest": digest,
                "canonical_json": canon,
            }
        )
    (OUT / "vectors.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(CASES)} cases to {OUT}")


if __name__ == "__main__":
    main()
