"""Resolve semantic certified-bundle identity hashes for trust-envelope checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def resolve_certified_bundle_identity_hash(
    release_dir: Path,
    *,
    manifest_artifacts: dict[str, Any] | None = None,
) -> str | None:
    """Bundle hash used by PF verification and handoff invariants (not always file sha256)."""
    release_dir = release_dir.resolve()

    for name in (
        "handoff_manifest.bundle_to_verifier.v0.json",
        "handoff_to_pf.json",
    ):
        doc = _load_json(release_dir / name)
        if not isinstance(doc, dict):
            continue
        invariants = doc.get("invariants")
        if isinstance(invariants, dict):
            value = invariants.get("certified_bundle_hash")
            if isinstance(value, str) and value:
                return value

    manifest = _load_json(release_dir / "release_manifest.v0.json")
    if isinstance(manifest, dict):
        chain_root = manifest.get("chain_root")
        if isinstance(chain_root, dict):
            value = chain_root.get("certified_bundle_hash")
            if isinstance(value, str) and value.startswith("sha256:"):
                verified = _load_json(release_dir / "verification_result.json")
                if isinstance(verified, dict):
                    vi = verified.get("verified_input")
                    if isinstance(vi, dict) and vi.get("bundle_hash") == value:
                        return value
        artifacts = manifest.get("artifacts")
        if isinstance(artifacts, dict):
            entry = artifacts.get("science_claim_bundle.certified.json")
            if isinstance(entry, dict):
                value = entry.get("sha256")
                if isinstance(value, str) and value:
                    return value

    if manifest_artifacts is not None:
        raw = manifest_artifacts.get("science_claim_bundle.certified.json")
        if isinstance(raw, str) and raw:
            return raw

    legacy = _load_json(release_dir / "RELEASE_FIXTURE_MANIFEST.json")
    if isinstance(legacy, dict):
        artifacts = legacy.get("artifacts")
        if isinstance(artifacts, dict):
            value = artifacts.get("science_claim_bundle.certified.json")
            if isinstance(value, str) and value:
                return value

    certified_path = release_dir / "science_claim_bundle.certified.json"
    if certified_path.is_file():
        import hashlib

        digest = hashlib.sha256(certified_path.read_bytes()).hexdigest()
        return f"sha256:{digest}"

    return None
