"""Canonical JSON hashing for PCS artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SIGNATURE_FIELD = "signature_or_digest"


def _sort_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sort_keys(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_sort_keys(item) for item in value]
    return value


def canonicalize_for_hash(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy suitable for hashing (signature removed, keys sorted)."""
    payload = dict(data)
    payload.pop(SIGNATURE_FIELD, None)
    sorted_payload = _sort_keys(payload)
    assert isinstance(sorted_payload, dict)
    return sorted_payload


def canonical_json_bytes(data: dict[str, Any]) -> bytes:
    canonical = canonicalize_for_hash(data)
    return json.dumps(canonical, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_hash(data: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(data)).hexdigest()
    return f"sha256:{digest}"
