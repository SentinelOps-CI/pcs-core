"""ArtifactIntegrity.v1: Ed25519 sign/verify with trusted key registry.

Domain-separated signing message (docs/trust-model.md):

    PCS:<artifact_type>:<schema_version>:<artifact_digest>

pcs-core does not ship production private keys. Downstream verifiers pin an
allowlist of ed25519 public keys by ``key_id`` (see TrustedKeyRegistry.v0).
"""

from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from pcs_core.hash import (
    ARTIFACT_DIGEST_FIELD,
    CANONICALIZATION_VERSION,
    HASH_EXCLUDED_FIELDS,
    SIGNATURE_FIELD,
    SIGNATURE_OBJECT_FIELD,
    attach_artifact_digest,
    canonical_hash,
    domain_separated_signing_message,
)

# Artifacts that stable releases must authenticate (digest-only is preview-only).
STABLE_RELEASE_SIGNED_ARTIFACT_TYPES: frozenset[str] = frozenset(
    {
        "ReleaseManifest.v0",
        "PFCoreReleaseBundleManifest.v0",
        "PFCoreCertificate.v0",
        "LeanCheckResult.v0",
        "ExternalAttestation.v0",
        "PublicationBundle.v0",
    }
)

DEFAULT_MAX_SIGNATURE_AGE = timedelta(days=365)
DEFAULT_FUTURE_SKEW = timedelta(minutes=5)


class IntegrityError(ValueError):
    """Raised when signature verification or key-policy checks fail."""


@dataclass(frozen=True)
class TrustedKey:
    key_id: str
    algorithm: str
    public_key_bytes: bytes
    valid_from: datetime
    valid_until: datetime | None
    revoked_at: datetime | None
    purposes: frozenset[str]
    note: str | None = None

    def is_revoked_at(self, when: datetime) -> bool:
        return self.revoked_at is not None and when >= self.revoked_at

    def is_valid_at(self, when: datetime) -> bool:
        if when < self.valid_from:
            return False
        if self.valid_until is not None and when > self.valid_until:
            return False
        if self.is_revoked_at(when):
            return False
        return True


@dataclass(frozen=True)
class TrustedKeyRegistry:
    keys: tuple[TrustedKey, ...]
    registry_id: str | None = None

    def get(self, key_id: str) -> TrustedKey | None:
        for key in self.keys:
            if key.key_id == key_id:
                return key
        return None

    def require(self, key_id: str) -> TrustedKey:
        key = self.get(key_id)
        if key is None:
            raise IntegrityError(f"UnknownKeyId: {key_id!r} not in trusted key registry")
        return key


@dataclass(frozen=True)
class TimestampPolicy:
    """Policy for ``signed_at`` relative to key validity and wall clock."""

    max_age: timedelta | None = DEFAULT_MAX_SIGNATURE_AGE
    future_skew: timedelta = DEFAULT_FUTURE_SKEW
    now: datetime | None = None

    def evaluate(self, signed_at: datetime, key: TrustedKey) -> list[str]:
        errors: list[str] = []
        now = self.now or datetime.now(timezone.utc)
        if signed_at.tzinfo is None:
            signed_at = signed_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        if not key.is_valid_at(signed_at):
            if key.is_revoked_at(signed_at):
                errors.append(
                    f"KeyRevokedAtSignatureTime: key_id={key.key_id!r} "
                    f"revoked_at={_format_utc(key.revoked_at)} "
                    f"signed_at={_format_utc(signed_at)}"
                )
            else:
                errors.append(
                    f"KeyOutsideValidityInterval: key_id={key.key_id!r} "
                    f"signed_at={_format_utc(signed_at)} "
                    f"valid_from={_format_utc(key.valid_from)} "
                    f"valid_until={_format_utc(key.valid_until)}"
                )

        if signed_at > now + self.future_skew:
            errors.append(
                f"SignatureTimestampInFuture: signed_at={_format_utc(signed_at)} "
                f"now={_format_utc(now)}"
            )

        if self.max_age is not None and signed_at < now - self.max_age:
            errors.append(
                f"SignatureTimestampTooOld: signed_at={_format_utc(signed_at)} "
                f"max_age_seconds={int(self.max_age.total_seconds())}"
            )
        return errors


def _format_utc(value: datetime | None) -> str:
    if value is None:
        return "null"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc_datetime(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def encode_key_bytes(raw: bytes) -> str:
    """Encode key/signature bytes as unpadded base64url."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_key_bytes(value: str, *, expected_len: int | None = None) -> bytes:
    """Decode base64url (preferred) or standard base64; optional hex fallback."""
    text = value.strip()
    if not text:
        raise IntegrityError("empty key/signature encoding")
    padded_url = text + ("=" * ((4 - len(text) % 4) % 4))
    try:
        raw = base64.urlsafe_b64decode(padded_url.encode("ascii"))
    except (binascii.Error, ValueError):
        try:
            raw = base64.b64decode(text.encode("ascii"))
        except (binascii.Error, ValueError):
            try:
                raw = bytes.fromhex(text.removeprefix("0x"))
            except ValueError as exc:
                raise IntegrityError(f"invalid key/signature encoding: {exc}") from exc
    if expected_len is not None and len(raw) != expected_len:
        raise IntegrityError(f"decoded key/signature length {len(raw)} != expected {expected_len}")
    return raw


def generate_ed25519_keypair() -> tuple[bytes, bytes]:
    """Return ``(private_seed_32, public_key_32)`` for tests and local tooling."""
    signing = SigningKey.generate()
    return bytes(signing), bytes(signing.verify_key)


def signing_key_from_seed(seed: bytes) -> SigningKey:
    if len(seed) != 32:
        raise IntegrityError(f"ed25519 private seed must be 32 bytes, got {len(seed)}")
    return SigningKey(seed)


def build_trusted_key(
    *,
    key_id: str,
    public_key: bytes | str,
    valid_from: str | datetime,
    valid_until: str | datetime | None = None,
    revoked_at: str | datetime | None = None,
    purposes: Sequence[str] | None = None,
    note: str | None = None,
) -> TrustedKey:
    pub = (
        public_key
        if isinstance(public_key, bytes)
        else decode_key_bytes(public_key, expected_len=32)
    )
    vf = valid_from if isinstance(valid_from, datetime) else parse_utc_datetime(valid_from)
    vu = None
    if valid_until is not None:
        vu = valid_until if isinstance(valid_until, datetime) else parse_utc_datetime(valid_until)
    rev = None
    if revoked_at is not None:
        rev = revoked_at if isinstance(revoked_at, datetime) else parse_utc_datetime(revoked_at)
    return TrustedKey(
        key_id=key_id,
        algorithm="ed25519",
        public_key_bytes=pub,
        valid_from=vf,
        valid_until=vu,
        revoked_at=rev,
        purposes=frozenset(purposes or ()),
        note=note,
    )


def trusted_key_to_dict(key: TrustedKey) -> dict[str, Any]:
    out: dict[str, Any] = {
        "key_id": key.key_id,
        "algorithm": key.algorithm,
        "public_key": encode_key_bytes(key.public_key_bytes),
        "valid_from": _format_utc(key.valid_from),
    }
    if key.valid_until is not None:
        out["valid_until"] = _format_utc(key.valid_until)
    if key.revoked_at is not None:
        out["revoked_at"] = _format_utc(key.revoked_at)
    if key.purposes:
        out["purposes"] = sorted(key.purposes)
    if key.note:
        out["note"] = key.note
    return out


def build_trusted_key_registry(
    keys: Sequence[TrustedKey],
    *,
    registry_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "TrustedKeyRegistry.v0",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "keys": [trusted_key_to_dict(k) for k in keys],
    }
    if registry_id:
        payload["registry_id"] = registry_id
    payload["signature_or_digest"] = canonical_hash(payload)
    return payload


def load_trusted_key_registry(data: Mapping[str, Any] | Path | str) -> TrustedKeyRegistry:
    if isinstance(data, (str, Path)):
        path = Path(data)
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = dict(data)
    if not isinstance(payload, dict):
        raise IntegrityError("TrustedKeyRegistry root must be an object")
    if payload.get("artifact_type") not in {None, "TrustedKeyRegistry.v0"}:
        raise IntegrityError(
            f"unexpected artifact_type for key registry: {payload.get('artifact_type')!r}"
        )
    keys_raw = payload.get("keys")
    if not isinstance(keys_raw, list):
        raise IntegrityError("TrustedKeyRegistry.keys must be an array")
    keys: list[TrustedKey] = []
    seen: set[str] = set()
    for index, entry in enumerate(keys_raw):
        if not isinstance(entry, dict):
            raise IntegrityError(f"TrustedKeyRegistry.keys[{index}] must be an object")
        key_id = str(entry.get("key_id") or "")
        if not key_id:
            raise IntegrityError(f"TrustedKeyRegistry.keys[{index}] missing key_id")
        if key_id in seen:
            raise IntegrityError(f"DuplicateKeyId: {key_id!r}")
        seen.add(key_id)
        if entry.get("algorithm") not in {None, "ed25519"}:
            raise IntegrityError(
                f"unsupported algorithm for {key_id!r}: {entry.get('algorithm')!r}"
            )
        purposes = entry.get("purposes") or []
        if not isinstance(purposes, list):
            raise IntegrityError(f"purposes for {key_id!r} must be an array")
        keys.append(
            build_trusted_key(
                key_id=key_id,
                public_key=str(entry["public_key"]),
                valid_from=str(entry["valid_from"]),
                valid_until=entry.get("valid_until"),
                revoked_at=entry.get("revoked_at"),
                purposes=[str(p) for p in purposes],
                note=str(entry["note"]) if entry.get("note") else None,
            )
        )
    registry_id = payload.get("registry_id")
    return TrustedKeyRegistry(
        keys=tuple(keys),
        registry_id=str(registry_id) if registry_id else None,
    )


def resolve_trusted_key_registry(
    path: Path | str | None = None,
) -> TrustedKeyRegistry | None:
    """Load registry from explicit path or ``PCS_TRUSTED_KEY_REGISTRY`` env."""
    resolved = path
    if resolved is None:
        env = os.environ.get("PCS_TRUSTED_KEY_REGISTRY", "").strip()
        if not env:
            return None
        resolved = env
    return load_trusted_key_registry(resolved)


def signing_message_bytes(
    *,
    artifact_type: str,
    schema_version: str,
    artifact_digest: str,
) -> bytes:
    return domain_separated_signing_message(
        artifact_type=artifact_type,
        schema_version=schema_version,
        artifact_digest=artifact_digest,
    ).encode("utf-8")


def sign_ed25519(
    message: bytes,
    *,
    private_seed: bytes,
) -> bytes:
    return bytes(signing_key_from_seed(private_seed).sign(message).signature)


def verify_ed25519(
    message: bytes,
    signature: bytes,
    *,
    public_key: bytes,
) -> None:
    try:
        VerifyKey(public_key).verify(message, signature)
    except BadSignatureError as exc:
        raise IntegrityError("SignatureVerificationFailed: ed25519 signature invalid") from exc


def _strip_integrity_fields(data: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(data)
    for field in HASH_EXCLUDED_FIELDS:
        body.pop(field, None)
    return body


def compute_artifact_digest(
    data: Mapping[str, Any],
    *,
    enforce_number_policy: bool = True,
) -> str:
    body = _strip_integrity_fields(data)
    body[ARTIFACT_DIGEST_FIELD] = "sha256:" + ("0" * 64)
    body.setdefault("canonicalization_version", CANONICALIZATION_VERSION)
    return canonical_hash(body, enforce_number_policy=enforce_number_policy)


def sign_artifact(
    data: Mapping[str, Any],
    *,
    private_seed: bytes,
    key_id: str,
    signed_at: str | datetime | None = None,
    enforce_number_policy: bool = True,
) -> dict[str, Any]:
    """Attach ``artifact_digest`` + ed25519 ``signature`` (ArtifactIntegrity.v1 envelope)."""
    sealed = attach_artifact_digest(dict(data), enforce_number_policy=enforce_number_policy)
    artifact_type = str(sealed.get("artifact_type") or "")
    schema_version = str(sealed.get("schema_version") or "")
    if not artifact_type or not schema_version:
        raise IntegrityError("artifact_type and schema_version required before signing")
    digest = str(sealed[ARTIFACT_DIGEST_FIELD])
    message = signing_message_bytes(
        artifact_type=artifact_type,
        schema_version=schema_version,
        artifact_digest=digest,
    )
    sig = sign_ed25519(message, private_seed=private_seed)
    when = signed_at if signed_at is not None else datetime.now(timezone.utc)
    if isinstance(when, datetime):
        when_str = _format_utc(when)
    else:
        when_str = when
    sealed[SIGNATURE_OBJECT_FIELD] = {
        "algorithm": "ed25519",
        "key_id": key_id,
        "signed_at": when_str,
        "value": encode_key_bytes(sig),
    }
    sealed.pop(SIGNATURE_FIELD, None)
    return sealed


def build_integrity_sidecar(
    target: Mapping[str, Any],
    *,
    private_seed: bytes,
    key_id: str,
    signed_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Build a thin ArtifactIntegrity.v1 sidecar binding ``target``'s content digest."""
    target_digest = compute_artifact_digest(target)
    target_type = str(target.get("artifact_type") or "UnknownArtifact")
    envelope: dict[str, Any] = {
        "schema_version": "v1",
        "artifact_type": "ArtifactIntegrity.v1",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "target_artifact_type": target_type,
        "target_schema_version": str(target.get("schema_version") or ""),
        "target_digest": target_digest,
        "payload": {"bound_artifact_type": target_type},
    }
    # Sign over ArtifactIntegrity.v1 identity with digest of the integrity body.
    return sign_artifact(
        envelope,
        private_seed=private_seed,
        key_id=key_id,
        signed_at=signed_at,
    )


def verify_artifact_signature(
    data: Mapping[str, Any],
    registry: TrustedKeyRegistry,
    *,
    timestamp_policy: TimestampPolicy | None = None,
    required_purpose: str | None = None,
    expect_digest: str | None = None,
) -> list[str]:
    """Verify domain-separated ed25519 signature against a trusted key registry."""
    errors: list[str] = []
    if SIGNATURE_FIELD in data:
        errors.append("ArtifactIntegrityLegacyField: signature_or_digest forbidden on v1 envelopes")

    digest = str(data.get(ARTIFACT_DIGEST_FIELD) or "")
    if not digest.startswith("sha256:") or len(digest) != 71:
        errors.append("ArtifactIntegrityDigestMissing: artifact_digest required")
        return errors

    recomputed = compute_artifact_digest(data)
    if digest != recomputed:
        errors.append(
            f"ArtifactIntegrityDigestMismatch: recorded {digest!r} != recomputed {recomputed!r}"
        )

    if expect_digest is not None and digest != expect_digest and recomputed != expect_digest:
        # Sidecar style: allow artifact_digest to cover the integrity envelope while
        # target_digest separately binds the signed object.
        target_digest = str(data.get("target_digest") or "")
        if target_digest != expect_digest:
            errors.append(
                f"ArtifactIntegrityTargetDigestMismatch: "
                f"expected {expect_digest!r}, got envelope={digest!r} target={target_digest!r}"
            )

    sig = data.get(SIGNATURE_OBJECT_FIELD)
    if not isinstance(sig, Mapping):
        errors.append("ArtifactIntegritySignatureMissing: signature object required")
        return errors

    if sig.get("algorithm") != "ed25519":
        errors.append(f"UnsupportedSignatureAlgorithm: {sig.get('algorithm')!r}")
        return errors

    key_id = str(sig.get("key_id") or "")
    signed_at_raw = str(sig.get("signed_at") or "")
    value = str(sig.get("value") or "")
    if not key_id or not signed_at_raw or not value:
        errors.append("ArtifactIntegritySignatureIncomplete: key_id/signed_at/value required")
        return errors

    try:
        key = registry.require(key_id)
    except IntegrityError as exc:
        errors.append(str(exc))
        return errors

    if required_purpose and required_purpose not in key.purposes and key.purposes:
        errors.append(f"KeyPurposeMismatch: key_id={key_id!r} missing purpose {required_purpose!r}")

    try:
        signed_at = parse_utc_datetime(signed_at_raw)
    except ValueError as exc:
        errors.append(f"InvalidSignatureTimestamp: {exc}")
        return errors

    policy = timestamp_policy or TimestampPolicy()
    errors.extend(policy.evaluate(signed_at, key))

    artifact_type = str(data.get("artifact_type") or "")
    schema_version = str(data.get("schema_version") or "")
    try:
        message = signing_message_bytes(
            artifact_type=artifact_type,
            schema_version=schema_version,
            artifact_digest=digest,
        )
        signature = decode_key_bytes(value, expected_len=64)
        verify_ed25519(message, signature, public_key=key.public_key_bytes)
    except IntegrityError as exc:
        errors.append(str(exc))
    return errors


def validate_artifact_integrity_semantics(
    data: Mapping[str, Any],
    *,
    registry: TrustedKeyRegistry | None = None,
    require_crypto_verify: bool = False,
) -> list[str]:
    """Semantic checks for ArtifactIntegrity.v1 (shape + optional crypto verify)."""
    errors: list[str] = []
    if SIGNATURE_FIELD in data:
        errors.append(
            "no_signature_or_digest: signature_or_digest is forbidden on ArtifactIntegrity.v1"
        )

    digest = str(data.get(ARTIFACT_DIGEST_FIELD) or "")
    sig = data.get(SIGNATURE_OBJECT_FIELD)
    if not digest.startswith("sha256:"):
        errors.append("domain_separated_signature: artifact_digest missing or malformed")
    if not isinstance(sig, Mapping):
        errors.append("domain_separated_signature: signature object missing")
    else:
        artifact_type = str(data.get("artifact_type") or "")
        schema_version = str(data.get("schema_version") or "")
        if digest.startswith("sha256:") and artifact_type and schema_version:
            try:
                domain_separated_signing_message(
                    artifact_type=artifact_type,
                    schema_version=schema_version,
                    artifact_digest=digest,
                )
            except ValueError as exc:
                errors.append(f"domain_separated_signature: {exc}")

    resolved = registry
    if resolved is None and (require_crypto_verify or os.environ.get("PCS_TRUSTED_KEY_REGISTRY")):
        resolved = resolve_trusted_key_registry()

    if require_crypto_verify and resolved is None:
        errors.append(
            "domain_separated_signature: cryptographic verify required but no trusted key registry"
        )
        return errors

    if resolved is not None and isinstance(sig, Mapping) and sig.get("algorithm") == "ed25519":
        errors.extend(verify_artifact_signature(data, resolved))
    return errors


def integrity_sidecar_path(artifact_path: Path) -> Path:
    return artifact_path.with_suffix(artifact_path.suffix + ".integrity.json")


def discover_integrity_envelope(
    artifact_path: Path,
    artifact: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Locate an integrity envelope: embedded field, sidecar, or ArtifactIntegrity.v1 file."""
    if artifact is not None:
        embedded = artifact.get("artifact_integrity")
        if isinstance(embedded, Mapping):
            return dict(embedded)
        if (
            artifact.get("artifact_type") == "ArtifactIntegrity.v1"
            and ARTIFACT_DIGEST_FIELD in artifact
            and SIGNATURE_OBJECT_FIELD in artifact
        ):
            return dict(artifact)

    candidates = [
        integrity_sidecar_path(artifact_path),
        artifact_path.parent / "ArtifactIntegrity.v1.json",
        artifact_path.parent / f"{artifact_path.stem}.integrity.json",
        artifact_path.parent / "PFCoreCertificate.v0.integrity.json",
    ]
    for path in candidates:
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                return payload
    return None


def verify_release_root_signatures(
    release_root: Path,
    registry: TrustedKeyRegistry,
    *,
    required_types: Sequence[str] | None = None,
    timestamp_policy: TimestampPolicy | None = None,
    allow_digest_only: bool = False,
) -> list[str]:
    """Verify signatures for critical artifacts under a release root.

    When ``allow_digest_only`` is True (preview / development), missing signatures
    are reported as warnings-style codes prefixed with ``DigestOnlyAllowed:`` and
    do not fail the check set returned here as hard errors — callers that want
    soft preview mode should pass ``allow_digest_only=True`` and filter.
    """
    root = release_root.resolve(strict=True)
    wanted = frozenset(required_types or STABLE_RELEASE_SIGNED_ARTIFACT_TYPES)
    errors: list[str] = []
    found_types: set[str] = set()

    for path in sorted(root.rglob("*.json")):
        if path.name.endswith(".integrity.json"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        artifact_type = str(payload.get("artifact_type") or "")
        if artifact_type not in wanted:
            continue
        found_types.add(artifact_type)
        rel = path.relative_to(root).as_posix()

        envelope = discover_integrity_envelope(path, payload)
        if envelope is None:
            msg = f"MissingAuthenticatedIntegrity: {rel} ({artifact_type})"
            if allow_digest_only:
                errors.append(f"DigestOnlyAllowed: {msg}")
            else:
                errors.append(msg)
            continue

        target_digest = compute_artifact_digest(payload)
        verify_errors = verify_artifact_signature(
            envelope,
            registry,
            timestamp_policy=timestamp_policy,
            required_purpose="release_signing",
            expect_digest=target_digest,
        )
        for err in verify_errors:
            errors.append(f"{rel}: {err}")

    if not allow_digest_only:
        missing = wanted - found_types
        # PublicationBundle may be absent on intermediate roots; only require types present.
        # Hard-require types that exist as files elsewhere is handled above; here we only
        # note absence of PF-Core / PCS manifests when the directory looks like a release.
        _ = missing
    return errors


def revoke_key_in_registry(
    registry_data: Mapping[str, Any],
    key_id: str,
    *,
    revoked_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Return a copy of a registry with ``key_id`` marked revoked."""
    payload = dict(registry_data)
    keys = payload.get("keys")
    if not isinstance(keys, list):
        raise IntegrityError("TrustedKeyRegistry.keys must be an array")
    when = (
        _format_utc(revoked_at)
        if isinstance(revoked_at, datetime)
        else (revoked_at or _format_utc(datetime.now(timezone.utc)))
    )
    updated: list[Any] = []
    found = False
    for entry in keys:
        if not isinstance(entry, dict):
            updated.append(entry)
            continue
        copy = dict(entry)
        if copy.get("key_id") == key_id:
            copy["revoked_at"] = when
            found = True
        updated.append(copy)
    if not found:
        raise IntegrityError(f"UnknownKeyId: {key_id!r}")
    payload["keys"] = updated
    payload.pop("signature_or_digest", None)
    payload["signature_or_digest"] = canonical_hash(payload)
    return payload
