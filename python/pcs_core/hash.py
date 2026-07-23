"""Canonical JSON hashing for PCS artifacts.

PCS Canonical JSON v1 (not full RFC 8785 JCS): existing cross-language digests
remain stable. See docs/hash-canonicalization.md.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

# v0 compatibility field: integrity digest mistaken historically for a signature.
SIGNATURE_FIELD = "signature_or_digest"
# v1 separated integrity digest (content hash) and cryptographic signature object.
ARTIFACT_DIGEST_FIELD = "artifact_digest"
SIGNATURE_OBJECT_FIELD = "signature"
# Fields stripped before hashing so digests/signatures do not cover themselves.
HASH_EXCLUDED_FIELDS = frozenset(
    {
        SIGNATURE_FIELD,
        ARTIFACT_DIGEST_FIELD,
        SIGNATURE_OBJECT_FIELD,
    }
)

CANONICALIZATION_VERSION = "v1"
PLACEHOLDER_DIGEST = f"sha256:{'0' * 64}"

# IEEE-754 / ECMAScript safe integer bounds (fallback number policy for v1).
SAFE_INTEGER_MIN = -9007199254740991
SAFE_INTEGER_MAX = 9007199254740991

# Normalized rejection codes shared with Rust and TypeScript release hashing.
REJECTION_FLOAT_PROHIBITED = "float_prohibited"
REJECTION_INTEGER_OUT_OF_RANGE = "integer_out_of_range"
REJECTION_NEGATIVE_ZERO = "negative_zero"


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented under Canonical JSON v1 rules."""

    def __init__(self, code: str, message: str, *, path: str = "$") -> None:
        self.code = code
        self.path = path
        super().__init__(message)


def domain_separated_signing_message(
    *,
    artifact_type: str,
    schema_version: str,
    artifact_digest: str,
) -> str:
    """Return the domain-separated message for signature verification.

    Format: ``PCS:<artifact_type>:<schema_version>:<artifact_digest>``
    """
    if not artifact_type or ":" in artifact_type:
        raise ValueError(f"invalid artifact_type for domain separation: {artifact_type!r}")
    if not schema_version or ":" in schema_version:
        raise ValueError(f"invalid schema_version for domain separation: {schema_version!r}")
    if not artifact_digest.startswith("sha256:") or len(artifact_digest) != 71:
        raise ValueError(f"invalid artifact_digest for domain separation: {artifact_digest!r}")
    return f"PCS:{artifact_type}:{schema_version}:{artifact_digest}"


def assert_canonical_number_policy(value: Any, *, path: str = "$") -> None:
    """Enforce Canonical JSON v1 number policy (strict / release hashing).

    Floats and negative zero are prohibited. Integers outside the safe-integer
    range are prohibited. Callers that must carry non-integer decimals should
    store them as normalized decimal strings rather than JSON numbers.
    """
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if value < SAFE_INTEGER_MIN or value > SAFE_INTEGER_MAX:
            raise CanonicalizationError(
                REJECTION_INTEGER_OUT_OF_RANGE,
                f"{path}: integer {value} outside safe-integer range "
                f"[{SAFE_INTEGER_MIN}, {SAFE_INTEGER_MAX}]",
                path=path,
            )
        return
    if isinstance(value, float):
        if value == 0.0 and math.copysign(1.0, value) < 0.0:
            raise CanonicalizationError(
                REJECTION_NEGATIVE_ZERO,
                f"{path}: negative zero is prohibited under Canonical JSON v1",
                path=path,
            )
        raise CanonicalizationError(
            REJECTION_FLOAT_PROHIBITED,
            f"{path}: float values are prohibited under Canonical JSON v1; "
            "use a normalized decimal string instead",
            path=path,
        )
    if isinstance(value, dict):
        for key, child in value.items():
            assert_canonical_number_policy(child, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            assert_canonical_number_policy(child, path=f"{path}[{index}]")


def _sort_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sort_keys(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_sort_keys(item) for item in value]
    return value


def canonicalize_for_hash(
    data: dict[str, Any],
    *,
    enforce_number_policy: bool = False,
) -> dict[str, Any]:
    """Return a copy suitable for hashing (integrity/signature fields removed, keys sorted)."""
    payload = {k: v for k, v in data.items() if k not in HASH_EXCLUDED_FIELDS}
    if enforce_number_policy:
        assert_canonical_number_policy(payload)
    sorted_payload = _sort_keys(payload)
    assert isinstance(sorted_payload, dict)
    return sorted_payload


def canonical_json_bytes(
    data: dict[str, Any],
    *,
    enforce_number_policy: bool = False,
) -> bytes:
    canonical = canonicalize_for_hash(data, enforce_number_policy=enforce_number_policy)
    return json.dumps(canonical, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_hash(
    data: dict[str, Any],
    *,
    enforce_number_policy: bool = False,
) -> str:
    digest = hashlib.sha256(
        canonical_json_bytes(data, enforce_number_policy=enforce_number_policy)
    ).hexdigest()
    return f"sha256:{digest}"


def canonical_hash_legacy(data: dict[str, Any]) -> str:
    """Hash without the strict number policy (Phase 0 / legacy digest compatibility)."""
    return canonical_hash(data, enforce_number_policy=False)


def canonical_hash_release(data: dict[str, Any]) -> str:
    """Hash with the strict number policy always enforced (release integrity envelopes)."""
    return canonical_hash(data, enforce_number_policy=True)


def try_canonical_hash_release(data: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return ``(digest, None)`` or ``(None, rejection_code)`` for cross-language vectors."""
    try:
        return canonical_hash_release(data), None
    except CanonicalizationError as exc:
        return None, exc.code


def attach_artifact_digest(
    data: dict[str, Any],
    *,
    enforce_number_policy: bool = True,
) -> dict[str, Any]:
    """Return a shallow copy with ``artifact_digest`` set under Canonical JSON v1."""
    body = dict(data)
    body.pop(SIGNATURE_FIELD, None)
    body.pop(SIGNATURE_OBJECT_FIELD, None)
    body[ARTIFACT_DIGEST_FIELD] = PLACEHOLDER_DIGEST
    body.setdefault("canonicalization_version", CANONICALIZATION_VERSION)
    digest = canonical_hash(body, enforce_number_policy=enforce_number_policy)
    body[ARTIFACT_DIGEST_FIELD] = digest
    return body
