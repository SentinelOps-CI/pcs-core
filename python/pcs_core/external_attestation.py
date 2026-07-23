"""External attestation artifacts bound to PF-Core release bundles."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from pcs_core.hash import CANONICALIZATION_VERSION, canonical_hash
from pcs_core.pf_core_certifyedge import (
    AttestationClass,
    CertificateCheckResult,
    classify_attestation_ref,
    run_certifyedge_check,
)
from pcs_core.pf_core_runtime import compute_trace_hash
from pcs_core.safe_paths import resolve_contained_file
from pcs_core.validate import ValidationError, validate_artifact, validate_schema

EMPTY_SHA256 = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
EXTERNAL_ATTESTATION_NAME = "external_attestation.json"
ABSENCE_NOTICE_NAME = "ABSENCE_OF_EXTERNAL_ATTESTATION.json"


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object root in {path}")
    return data


def file_sha256_digest(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def release_bundle_digest_from_manifest(manifest: Mapping[str, Any]) -> str:
    """Canonical release-bundle digest is the closed manifest signature_or_digest."""
    digest = str(manifest.get("signature_or_digest") or "")
    if not digest.startswith("sha256:"):
        raise ValueError("release bundle manifest missing signature_or_digest digest")
    recomputed = canonical_hash(dict(manifest))
    if recomputed != digest:
        raise ValueError(
            f"manifest digest mismatch: recorded {digest!r} != recomputed {recomputed!r}"
        )
    return digest


def policy_digest_from_property(property_id: str, property_version: str) -> str:
    payload = {
        "property_id": property_id,
        "property_version": property_version,
        "schema": "ExternalAttestation.v0.policy",
    }
    return canonical_hash(payload)


def _attestation_payload_for_digest(attestation: Mapping[str, Any]) -> dict[str, Any]:
    """Fields hashed into signature_or_digest (excludes signature_or_digest itself)."""
    payload = dict(attestation)
    payload.pop("signature_or_digest", None)
    return payload


def seal_external_attestation(
    attestation: dict[str, Any],
    *,
    private_seed: bytes | None = None,
    key_id: str | None = None,
    signed_at: str | None = None,
) -> dict[str, Any]:
    """Attach digest-bound attestation_signature and signature_or_digest.

    When ``private_seed`` and ``key_id`` are provided (or authentication_mode is
    already ``ed25519_signed`` with seed available via env), seal with a real
    Ed25519 signature over the domain-separated content digest message.
    """
    sealed = dict(attestation)
    sealed.setdefault("canonicalization_version", CANONICALIZATION_VERSION)
    sealed.pop("signature_or_digest", None)
    provisional = dict(sealed)
    provisional.pop("attestation_signature", None)
    content_digest = canonical_hash(provisional)
    mode = str(sealed.get("authentication_mode") or "digest_bound")

    seed = private_seed
    kid = key_id
    if seed is None:
        import os

        env_seed = os.environ.get("PCS_RELEASE_SIGNING_SEED_B64", "").strip()
        env_kid = os.environ.get("PCS_RELEASE_SIGNING_KEY_ID", "").strip()
        if env_seed and env_kid:
            from pcs_core.artifact_integrity import decode_key_bytes

            seed = decode_key_bytes(env_seed, expected_len=32)
            kid = kid or env_kid
            mode = "ed25519_signed"

    if mode == "ed25519_signed" and seed is not None and kid:
        from datetime import datetime, timezone

        from pcs_core.artifact_integrity import (
            encode_key_bytes,
            sign_ed25519,
            signing_message_bytes,
        )

        when = signed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
        message = signing_message_bytes(
            artifact_type="ExternalAttestation.v0",
            schema_version="v0",
            artifact_digest=content_digest,
        )
        sig = sign_ed25519(message, private_seed=seed)
        sealed["authentication_mode"] = "ed25519_signed"
        sealed["attestation_signature"] = {
            "algorithm": "ed25519",
            "key_id": kid,
            "signed_at": when,
            "value": encode_key_bytes(sig),
        }
    else:
        sealed["authentication_mode"] = "digest_bound"
        sealed["attestation_signature"] = {
            "algorithm": "sha256-digest-bound",
            "digest": content_digest,
            "note": (
                "Digest-bound integrity only. Replace with ed25519_signed once "
                "org CertifyEdge / release signing keys are configured "
                "(PCS_RELEASE_SIGNING_SEED_B64 + PCS_RELEASE_SIGNING_KEY_ID)."
            ),
        }
    sealed["signature_or_digest"] = canonical_hash(_attestation_payload_for_digest(sealed))
    return sealed


def build_external_attestation(
    *,
    release_bundle_digest: str,
    trace_digest: str,
    property_id: str,
    property_version: str = "v0",
    checker: str,
    checker_version: str,
    checker_binary_digest: str,
    result: str,
    attestation_class: AttestationClass,
    issuer_identity: str,
    attestation_ref: str | None = None,
    certificate_path: str | None = None,
    bundle_trace_path: str = "trace.json",
    executed_at: str | None = None,
    authentication_mode: str = "digest_bound",
) -> dict[str, Any]:
    """Build a sealed ExternalAttestation.v0 object."""
    if result not in {"CertificateChecked", "Rejected"}:
        raise ValueError(f"invalid attestation result: {result!r}")
    if attestation_class not in {"live", "stub", "mock"}:
        raise ValueError(f"invalid attestation_class: {attestation_class!r}")
    if attestation_class == "live" and result != "CertificateChecked":
        raise ValueError("live attestation_class requires CertificateChecked result")
    if attestation_class == "live" and attestation_ref:
        cls = classify_attestation_ref(attestation_ref)
        if cls in {"mock", "stub"}:
            raise ValueError(f"live attestation cannot use {cls} attestation_ref")

    payload: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "ExternalAttestation.v0",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "attestation_id": f"ext-attest-{uuid4().hex[:16]}",
        "release_bundle_digest": release_bundle_digest,
        "trace_digest": trace_digest,
        "property_id": property_id,
        "property_version": property_version,
        "checker": checker,
        "checker_version": checker_version,
        "checker_binary_digest": checker_binary_digest or EMPTY_SHA256,
        "policy_digest": policy_digest_from_property(property_id, property_version),
        "executed_at": executed_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "result": result,
        "attestation_class": attestation_class,
        "issuer_identity": issuer_identity,
        "authentication_mode": authentication_mode,
        "bundle_trace_path": bundle_trace_path,
    }
    if attestation_ref:
        payload["attestation_ref"] = attestation_ref
    if certificate_path:
        payload["certificate_path"] = certificate_path
    return seal_external_attestation(payload)


def build_absence_of_external_attestation_notice(
    *,
    release_bundle_digest: str,
    reason: str,
    release_mode: str = "preview",
) -> dict[str, Any]:
    """Explicit preview notice when live external attestation is absent."""
    notice = {
        "schema_version": "v0",
        "artifact_type": "AbsenceOfExternalAttestation.v0",
        "release_mode": release_mode,
        "release_bundle_digest": release_bundle_digest,
        "notice": (
            "Technical preview: this release bundle does NOT include a live "
            "external CertifyEdge attestation. Do not treat CertificateChecked "
            "claims as production-grade without ExternalAttestation.v0."
        ),
        "reason": reason,
        "recorded_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    notice["signature_or_digest"] = canonical_hash(notice)
    return notice


def validate_external_attestation(
    attestation: Mapping[str, Any],
    *,
    expected_bundle_digest: str | None = None,
    expected_trace_digest: str | None = None,
    require_live: bool = False,
    require_pinned_checker: bool = False,
    key_registry: Any | None = None,
) -> list[str]:
    """Schema + binding validation for ExternalAttestation.v0."""
    errors = validate_schema(dict(attestation), "ExternalAttestation.v0")
    if errors:
        return errors
    try:
        validate_artifact(dict(attestation), "ExternalAttestation.v0", release_grade=True)
    except ValidationError as exc:
        return list(exc.errors or [str(exc)])

    errors = []
    recomputed = canonical_hash(_attestation_payload_for_digest(attestation))
    recorded = str(attestation.get("signature_or_digest") or "")
    if recorded != recomputed:
        errors.append(
            f"ExternalAttestationDigestMismatch: {recorded!r} != recomputed {recomputed!r}"
        )

    if (
        expected_bundle_digest
        and attestation.get("release_bundle_digest") != expected_bundle_digest
    ):
        errors.append(
            "ExternalAttestationBundleMismatch: "
            f"{attestation.get('release_bundle_digest')!r} != {expected_bundle_digest!r}"
        )
    if expected_trace_digest and attestation.get("trace_digest") != expected_trace_digest:
        errors.append(
            "ExternalAttestationTraceMismatch: "
            f"{attestation.get('trace_digest')!r} != {expected_trace_digest!r}"
        )

    attestation_class = str(attestation.get("attestation_class") or "")
    if require_live:
        if attestation_class != "live":
            errors.append(f"ExternalAttestationNotLive: attestation_class={attestation_class!r}")
        ref = str(attestation.get("attestation_ref") or "")
        if ref.startswith("mock://") or ref.startswith("stub://"):
            errors.append(f"ExternalAttestationRefRejected: {ref}")
        if attestation.get("result") != "CertificateChecked":
            errors.append(
                "ExternalAttestationResultRejected: live gate requires CertificateChecked"
            )

    mode = str(attestation.get("authentication_mode") or "")
    sig = attestation.get("attestation_signature")
    if mode == "digest_bound":
        if not isinstance(sig, dict) or sig.get("algorithm") != "sha256-digest-bound":
            errors.append("ExternalAttestationSignatureModeMismatch: expected digest_bound marker")
    elif mode == "ed25519_signed":
        if not isinstance(sig, dict) or sig.get("algorithm") != "ed25519":
            errors.append("ExternalAttestationSignatureModeMismatch: expected ed25519 envelope")
        else:
            from pcs_core.artifact_integrity import (
                IntegrityError,
                TimestampPolicy,
                decode_key_bytes,
                load_trusted_key_registry,
                parse_utc_datetime,
                resolve_trusted_key_registry,
                signing_message_bytes,
                verify_ed25519,
            )

            registry = key_registry
            if registry is None:
                registry = resolve_trusted_key_registry()
            if registry is None:
                errors.append(
                    "ExternalAttestationSignatureUnverified: "
                    "ed25519_signed requires PCS_TRUSTED_KEY_REGISTRY"
                )
            else:
                if not hasattr(registry, "require"):
                    registry = load_trusted_key_registry(registry)
                provisional = dict(attestation)
                provisional.pop("attestation_signature", None)
                provisional.pop("signature_or_digest", None)
                content_digest = canonical_hash(provisional)
                try:
                    key = registry.require(str(sig.get("key_id") or ""))
                    message = signing_message_bytes(
                        artifact_type="ExternalAttestation.v0",
                        schema_version="v0",
                        artifact_digest=content_digest,
                    )
                    verify_ed25519(
                        message,
                        decode_key_bytes(str(sig.get("value") or ""), expected_len=64),
                        public_key=key.public_key_bytes,
                    )
                    policy_errors = TimestampPolicy().evaluate(
                        parse_utc_datetime(str(sig.get("signed_at") or "")),
                        key,
                    )
                    errors.extend(policy_errors)
                except IntegrityError as exc:
                    errors.append(str(exc))
                except ValueError as exc:
                    errors.append(f"ExternalAttestationSignatureInvalid: {exc}")

    from pcs_core.certifyedge_pin import validate_attestation_against_pin

    errors.extend(
        validate_attestation_against_pin(
            attestation,
            require_pinned=require_pinned_checker,
        )
    )

    return errors


def attest_release_bundle(
    bundle_dir: Path,
    *,
    property_id: str,
    property_version: str = "v0",
    require_live: bool = False,
    checker_version: str = "0.1.0",
    write: bool = True,
) -> tuple[dict[str, Any], CertificateCheckResult]:
    """Run CertifyEdge against the exact bundle trace and emit ExternalAttestation.v0."""
    bundle_root = bundle_dir.resolve(strict=True)
    manifest_path = resolve_contained_file(
        bundle_root, "manifest.json", allowed_suffixes=frozenset({".json"})
    )
    manifest = _load_json(manifest_path)
    bundle_digest = release_bundle_digest_from_manifest(manifest)

    trace_rel = str(manifest.get("trace_path") or "trace.json")
    trace_path = resolve_contained_file(
        bundle_root, trace_rel, allowed_suffixes=frozenset({".json"})
    )
    trace = _load_json(trace_path)
    trace_digest = str(trace.get("trace_hash") or compute_trace_hash(trace))

    check = run_certifyedge_check(
        trace_path,
        property_id,
        checker_version=checker_version,
        require_live=require_live,
    )
    attestation_class: AttestationClass = check.attestation_class or (
        classify_attestation_ref(check.attestation_ref) or ("live" if check.ok else "mock")
    )
    # Never emit a live+Rejected pair: live class is reserved for CertificateChecked results.
    if not check.ok and attestation_class == "live":
        attestation_class = classify_attestation_ref(check.attestation_ref) or "mock"
    if require_live and (not check.ok or attestation_class != "live"):
        raise RuntimeError(
            f"live external attestation failed for bundle {bundle_root}: {check.message}"
        )

    cli = None
    try:
        from pcs_core.pf_core_certifyedge import _find_format_stub, _find_live_certifyedge_cli

        cli = _find_live_certifyedge_cli() or _find_format_stub()
    except Exception:
        cli = None

    from pcs_core.certifyedge_pin import (
        classify_checker_trust,
        load_certifyedge_pin,
        load_provision_environment,
    )

    provision = load_provision_environment()
    pin = None
    try:
        pin = load_certifyedge_pin()
    except Exception:
        pin = None

    trust_grade = classify_checker_trust(
        executable=Path(cli) if cli else None,
        pin=pin,
        provision=provision,
    )
    if require_live and trust_grade == "untrusted_development":
        raise RuntimeError(
            "live external attestation rejected: checker trust_grade=untrusted_development "
            "(arbitrary PATH executables and dev fixtures are not release-grade; "
            "provision from a production pin and source provision.env)"
        )

    if provision is not None and Path(provision.executable_path).is_file():
        checker_binary_digest = provision.binary_digest
        issuer = f"certifyedge-binary:{checker_binary_digest}"
        if provision.pin_identity:
            issuer = f"{issuer};pin={provision.pin_identity}"
    elif cli and Path(cli).is_file() and Path(cli).suffix != ".py":
        checker_binary_digest = file_sha256_digest(Path(cli))
        issuer = f"certifyedge-binary:{checker_binary_digest}"
        if trust_grade != "pinned":
            issuer = f"{issuer};trust_grade={trust_grade}"
    elif cli:
        checker_binary_digest = EMPTY_SHA256
        issuer = f"certifyedge-stub:{Path(cli).name}"
    else:
        checker_binary_digest = EMPTY_SHA256
        issuer = "certifyedge-mock"

    cert_rel: str | None = None
    if check.ok and check.certificate is not None:
        cert_path = bundle_root / "certificate.external.json"
        cert_path.write_text(json.dumps(check.certificate, indent=2) + "\n", encoding="utf-8")
        cert_rel = cert_path.name

    attestation = build_external_attestation(
        release_bundle_digest=bundle_digest,
        trace_digest=trace_digest,
        property_id=property_id,
        property_version=property_version,
        checker=check.checker,
        checker_version=check.checker_version,
        checker_binary_digest=checker_binary_digest,
        result="CertificateChecked" if check.ok else "Rejected",
        attestation_class=attestation_class,
        issuer_identity=issuer,
        attestation_ref=check.attestation_ref,
        certificate_path=cert_rel,
        bundle_trace_path=trace_rel,
    )
    binding_errors = validate_external_attestation(
        attestation,
        expected_bundle_digest=bundle_digest,
        expected_trace_digest=trace_digest,
        require_live=require_live,
    )
    if binding_errors:
        raise RuntimeError("; ".join(binding_errors))

    if write:
        out = bundle_root / EXTERNAL_ATTESTATION_NAME
        out.write_text(json.dumps(attestation, indent=2) + "\n", encoding="utf-8")
        # Remove any prior absence notice when attestation is present.
        notice = bundle_root / ABSENCE_NOTICE_NAME
        if notice.is_file():
            notice.unlink()
    return attestation, check


def write_preview_absence_notice(bundle_dir: Path, *, reason: str) -> Path:
    """Write explicit absence notice for technical preview bundles."""
    bundle_root = bundle_dir.resolve(strict=True)
    manifest = _load_json(
        resolve_contained_file(bundle_root, "manifest.json", allowed_suffixes=frozenset({".json"}))
    )
    digest = release_bundle_digest_from_manifest(manifest)
    notice = build_absence_of_external_attestation_notice(
        release_bundle_digest=digest,
        reason=reason,
        release_mode="preview",
    )
    out = bundle_root / ABSENCE_NOTICE_NAME
    out.write_text(json.dumps(notice, indent=2) + "\n", encoding="utf-8")
    return out


def validate_bundle_external_attestation(
    bundle_dir: Path,
    *,
    require_live: bool = False,
    allow_absence_notice: bool = False,
) -> list[str]:
    """Validate external attestation (or preview absence notice) in a bundle."""
    bundle_root = bundle_dir.resolve(strict=True)
    manifest = _load_json(
        resolve_contained_file(bundle_root, "manifest.json", allowed_suffixes=frozenset({".json"}))
    )
    bundle_digest = release_bundle_digest_from_manifest(manifest)
    trace_rel = str(manifest.get("trace_path") or "trace.json")
    trace = _load_json(
        resolve_contained_file(bundle_root, trace_rel, allowed_suffixes=frozenset({".json"}))
    )
    trace_digest = str(trace.get("trace_hash") or compute_trace_hash(trace))

    attest_path = bundle_root / EXTERNAL_ATTESTATION_NAME
    notice_path = bundle_root / ABSENCE_NOTICE_NAME

    if attest_path.is_file():
        attestation = _load_json(attest_path)
        return validate_external_attestation(
            attestation,
            expected_bundle_digest=bundle_digest,
            expected_trace_digest=trace_digest,
            require_live=require_live,
        )

    if require_live:
        return [
            "ExternalAttestationMissing: release mode requires "
            f"{EXTERNAL_ATTESTATION_NAME} with attestation_class=live"
        ]

    if allow_absence_notice and notice_path.is_file():
        notice = _load_json(notice_path)
        if notice.get("artifact_type") != "AbsenceOfExternalAttestation.v0":
            return ["AbsenceNoticeInvalid: unexpected artifact_type"]
        if notice.get("release_bundle_digest") != bundle_digest:
            return ["AbsenceNoticeBundleMismatch"]
        if "does NOT include a live" not in str(notice.get("notice") or ""):
            return ["AbsenceNoticeIncomplete: missing explicit absence language"]
        return []

    if allow_absence_notice:
        return [
            f"ExternalAttestationOrNoticeMissing: expected {EXTERNAL_ATTESTATION_NAME} "
            f"or {ABSENCE_NOTICE_NAME} for preview"
        ]
    return [f"ExternalAttestationMissing: {EXTERNAL_ATTESTATION_NAME} not found"]
