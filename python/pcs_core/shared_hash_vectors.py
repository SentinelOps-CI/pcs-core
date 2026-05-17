"""Shared canonical hash vectors for Python, Rust, and TypeScript."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.hash import canonical_hash, canonical_json_bytes
from pcs_core.paths import repo_root

VECTOR_SPECS: dict[str, str] = {
    "RuntimeReceipt.v0": "runtime_receipt.valid.json",
    "TraceCertificate.v0": "trace_certificate.valid.json",
    "ScienceClaimBundle.v0": "science_claim_bundle.certified.valid.json",
    "SignedScienceClaimBundle.v0": "signed_science_claim_bundle.valid.json",
    "ReleaseManifest.v0": "release_manifest.valid.json",
    "HandoffManifest.v0": "handoff_manifest.valid.json",
}


def shared_vectors_dir() -> Path:
    return repo_root() / "test_vectors" / "hash"


def vector_path(artifact_type: str) -> Path:
    slug = artifact_type.replace(".v0", "").replace(".", "_").lower()
    return shared_vectors_dir() / f"{slug}.vector.json"


def load_vector(artifact_type: str) -> dict[str, Any]:
    path = vector_path(artifact_type)
    return json.loads(path.read_text(encoding="utf-8"))


def write_shared_vectors(*, force: bool = False) -> None:
    from pcs_core.paths import examples_dir

    out_dir = shared_vectors_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    examples = examples_dir()
    for artifact_type, example_name in VECTOR_SPECS.items():
        path = out_dir / vector_path(artifact_type).name
        if path.exists() and not force:
            continue
        data = json.loads((examples / example_name).read_text(encoding="utf-8"))
        payload = {
            "artifact_type": artifact_type,
            "input_file": example_name,
            "expected_digest": canonical_hash(data),
            "canonical_json": canonical_json_bytes(data).decode("utf-8"),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def verify_shared_vectors() -> list[str]:
    from pcs_core.paths import examples_dir

    errors: list[str] = []
    examples = examples_dir()
    for artifact_type in VECTOR_SPECS:
        vector = load_vector(artifact_type)
        example_name = vector.get("input_file", VECTOR_SPECS[artifact_type])
        data = json.loads((examples / str(example_name)).read_text(encoding="utf-8"))
        expected_digest = str(vector["expected_digest"])
        expected_canonical = str(vector["canonical_json"])
        actual_digest = canonical_hash(data)
        actual_canonical = canonical_json_bytes(data).decode("utf-8")
        if actual_digest != expected_digest:
            errors.append(
                f"{artifact_type}: digest mismatch "
                f"(expected {expected_digest}, got {actual_digest})",
            )
        if actual_canonical != expected_canonical:
            errors.append(f"{artifact_type}: canonical JSON drift")
    return errors
