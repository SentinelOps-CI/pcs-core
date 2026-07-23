"""ArtifactIntegrity.v1 Ed25519 sign/verify and key-revocation tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pcs_core.artifact_integrity import (
    IntegrityError,
    TimestampPolicy,
    build_integrity_sidecar,
    build_trusted_key,
    build_trusted_key_registry,
    encode_key_bytes,
    generate_ed25519_keypair,
    load_trusted_key_registry,
    revoke_key_in_registry,
    sign_artifact,
    validate_artifact_integrity_semantics,
    verify_artifact_signature,
    verify_release_root_signatures,
)
from pcs_core.validate import validate_artifact


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def test_ed25519_sign_and_verify_roundtrip() -> None:
    seed, pub = generate_ed25519_keypair()
    key_id = "test-release-key-1"
    registry = load_trusted_key_registry(
        build_trusted_key_registry(
            [
                build_trusted_key(
                    key_id=key_id,
                    public_key=pub,
                    valid_from=_utcnow() - timedelta(days=1),
                    purposes=["release_signing"],
                )
            ],
            registry_id="test-registry",
        )
    )
    body = {
        "schema_version": "v1",
        "artifact_type": "ArtifactIntegrity.v1",
        "payload": {"ok": True, "n": 1},
    }
    sealed = sign_artifact(body, private_seed=seed, key_id=key_id, signed_at=_utcnow())
    validate_artifact(sealed, "ArtifactIntegrity.v1", release_grade=True)
    errors = verify_artifact_signature(sealed, registry, required_purpose="release_signing")
    assert errors == []
    semantic = validate_artifact_integrity_semantics(sealed, registry=registry)
    assert semantic == []


def test_tampered_payload_fails_verify() -> None:
    seed, pub = generate_ed25519_keypair()
    key_id = "k1"
    registry = load_trusted_key_registry(
        build_trusted_key_registry(
            [
                build_trusted_key(
                    key_id=key_id,
                    public_key=pub,
                    valid_from=_utcnow() - timedelta(days=1),
                )
            ]
        )
    )
    sealed = sign_artifact(
        {
            "schema_version": "v1",
            "artifact_type": "ArtifactIntegrity.v1",
            "payload": {"ok": True},
        },
        private_seed=seed,
        key_id=key_id,
    )
    tampered = dict(sealed)
    tampered["payload"] = {"ok": False}
    errors = verify_artifact_signature(tampered, registry)
    assert any("DigestMismatch" in e or "SignatureVerificationFailed" in e for e in errors)


def test_revoked_key_rejected() -> None:
    seed, pub = generate_ed25519_keypair()
    key_id = "revocable"
    now = _utcnow()
    registry_doc = build_trusted_key_registry(
        [
            build_trusted_key(
                key_id=key_id,
                public_key=pub,
                valid_from=now - timedelta(days=30),
                purposes=["release_signing"],
            )
        ]
    )
    sealed = sign_artifact(
        {
            "schema_version": "v1",
            "artifact_type": "ArtifactIntegrity.v1",
            "payload": {"x": 1},
        },
        private_seed=seed,
        key_id=key_id,
        signed_at=now,
    )
    assert verify_artifact_signature(sealed, load_trusted_key_registry(registry_doc)) == []

    revoked_doc = revoke_key_in_registry(registry_doc, key_id, revoked_at=now - timedelta(hours=1))
    revoked_registry = load_trusted_key_registry(revoked_doc)
    errors = verify_artifact_signature(
        sealed,
        revoked_registry,
        timestamp_policy=TimestampPolicy(now=now),
    )
    assert any("KeyRevoked" in e for e in errors)


def test_key_outside_validity_interval() -> None:
    seed, pub = generate_ed25519_keypair()
    key_id = "windowed"
    now = _utcnow()
    registry = load_trusted_key_registry(
        build_trusted_key_registry(
            [
                build_trusted_key(
                    key_id=key_id,
                    public_key=pub,
                    valid_from=now - timedelta(days=10),
                    valid_until=now - timedelta(days=1),
                )
            ]
        )
    )
    sealed = sign_artifact(
        {
            "schema_version": "v1",
            "artifact_type": "ArtifactIntegrity.v1",
            "payload": {"x": 1},
        },
        private_seed=seed,
        key_id=key_id,
        signed_at=now,
    )
    errors = verify_artifact_signature(
        sealed,
        registry,
        timestamp_policy=TimestampPolicy(now=now),
    )
    assert any("KeyOutsideValidityInterval" in e for e in errors)


def test_unknown_key_id_rejected() -> None:
    seed, pub = generate_ed25519_keypair()
    registry = load_trusted_key_registry(
        build_trusted_key_registry(
            [
                build_trusted_key(
                    key_id="other",
                    public_key=pub,
                    valid_from=_utcnow() - timedelta(days=1),
                )
            ]
        )
    )
    sealed = sign_artifact(
        {
            "schema_version": "v1",
            "artifact_type": "ArtifactIntegrity.v1",
            "payload": {},
        },
        private_seed=seed,
        key_id="missing",
    )
    errors = verify_artifact_signature(sealed, registry)
    assert any("UnknownKeyId" in e for e in errors)


def test_signature_timestamp_too_old() -> None:
    seed, pub = generate_ed25519_keypair()
    key_id = "aged"
    now = _utcnow()
    registry = load_trusted_key_registry(
        build_trusted_key_registry(
            [
                build_trusted_key(
                    key_id=key_id,
                    public_key=pub,
                    valid_from=now - timedelta(days=400),
                )
            ]
        )
    )
    sealed = sign_artifact(
        {
            "schema_version": "v1",
            "artifact_type": "ArtifactIntegrity.v1",
            "payload": {},
        },
        private_seed=seed,
        key_id=key_id,
        signed_at=now - timedelta(days=400),
    )
    errors = verify_artifact_signature(
        sealed,
        registry,
        timestamp_policy=TimestampPolicy(max_age=timedelta(days=30), now=now),
    )
    assert any("SignatureTimestampTooOld" in e for e in errors)


def test_integrity_sidecar_binds_target(tmp_path: Path) -> None:
    seed, pub = generate_ed25519_keypair()
    key_id = "side"
    registry = load_trusted_key_registry(
        build_trusted_key_registry(
            [
                build_trusted_key(
                    key_id=key_id,
                    public_key=pub,
                    valid_from=_utcnow() - timedelta(days=1),
                    purposes=["release_signing"],
                )
            ]
        )
    )
    target = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": "c1",
        "claim_class": "LeanKernelChecked",
        "payload_note": "minimal-for-digest",
    }
    sidecar = build_integrity_sidecar(target, private_seed=seed, key_id=key_id)
    from pcs_core.artifact_integrity import compute_artifact_digest

    errors = verify_artifact_signature(
        sidecar,
        registry,
        expect_digest=compute_artifact_digest(target),
    )
    assert errors == []

    root = tmp_path / "release"
    root.mkdir()
    cert_path = root / "certificate.json"
    cert_path.write_text(
        __import__("json").dumps(target),
        encoding="utf-8",
    )
    (root / "certificate.json.integrity.json").write_text(
        __import__("json").dumps(sidecar),
        encoding="utf-8",
    )
    # Digest-only preview path reports soft codes when allow_digest_only.
    soft = verify_release_root_signatures(root, registry, allow_digest_only=True)
    # Sidecar present → should verify cleanly (no MissingAuthenticatedIntegrity).
    assert not any(e.startswith("MissingAuthenticatedIntegrity") for e in soft)


def test_trusted_key_registry_schema_roundtrip() -> None:
    _, pub = generate_ed25519_keypair()
    doc = build_trusted_key_registry(
        [
            build_trusted_key(
                key_id="k",
                public_key=encode_key_bytes(pub),
                valid_from="2026-01-01T00:00:00Z",
                purposes=["development"],
            )
        ],
        registry_id="dev",
    )
    validate_artifact(doc, "TrustedKeyRegistry.v0", release_grade=True)
    loaded = load_trusted_key_registry(doc)
    assert loaded.get("k") is not None


def test_revoke_unknown_key_raises() -> None:
    doc = build_trusted_key_registry([])
    with pytest.raises(IntegrityError, match="UnknownKeyId"):
        revoke_key_in_registry(doc, "nope")
