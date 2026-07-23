"""PCSProjectionManifest.v0: bind extracted proof fields to artifact digests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from jsonpointer import JsonPointerException, resolve_pointer

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.obligation_extraction_errors import (
    InvalidProofInputDigest,
    ObligationExtractionError,
)

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_UNKNOWN_RE = re.compile(r"(?i)(^|[^a-z0-9])unknown([^a-z0-9]|$)")
_FORBIDDEN_VALUE_RE = re.compile(
    r"(?i)^(cert-unknown|release-unknown|proof-obligation-unknown|witness-unknown|unknown)$"
)
_LEAN_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")

# Versioned synthetic-resolver registry (B1). Digests bind resolver identity + resolved value.
PROJECTION_RESOLVER_REGISTRY_VERSION = "v0"
CERTIFIED_BUNDLE_RESOLVER_ID = "#resolved/certified_bundle_hash"

# Synthetic JSON Pointer: normalized_value is the SHA-256 of the artifact file bytes (B3).
PAYLOAD_SHA256_POINTER = "/#payload_sha256"


@dataclass(frozen=True)
class SyntheticResolverSpec:
    """Registered synthetic projection source (not a filesystem artifact)."""

    resolver_id: str
    version: str
    description: str
    resolve: Callable[[Path], str]


def _resolve_certified_bundle_identity(release_dir: Path) -> str:
    from pcs_core.bundle_identity import resolve_certified_bundle_identity_hash

    value = resolve_certified_bundle_identity_hash(release_dir)
    if not isinstance(value, str) or not value:
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message="certified bundle identity could not be resolved",
            artifact=CERTIFIED_BUNDLE_RESOLVER_ID,
            field_path="/#resolved/certified_bundle_hash",
        )
    return require_sha256_digest(
        value,
        field="/#resolved/certified_bundle_hash",
        artifact=CERTIFIED_BUNDLE_RESOLVER_ID,
    )


SYNTHETIC_RESOLVER_REGISTRY: dict[str, SyntheticResolverSpec] = {
    CERTIFIED_BUNDLE_RESOLVER_ID: SyntheticResolverSpec(
        resolver_id=CERTIFIED_BUNDLE_RESOLVER_ID,
        version=PROJECTION_RESOLVER_REGISTRY_VERSION,
        description=(
            "Certified bundle identity hash resolved from handoff invariants, "
            "release-manifest chain_root, or certified bundle artifact digest"
        ),
        resolve=_resolve_certified_bundle_identity,
    ),
}


@dataclass(frozen=True)
class ProjectionEntry:
    artifact_path: str
    artifact_digest: str
    json_pointer: str
    normalized_value: str
    lean_identifier: str

    def to_dict(self) -> dict[str, str]:
        return {
            "artifact_path": self.artifact_path,
            "artifact_digest": self.artifact_digest,
            "json_pointer": self.json_pointer,
            "normalized_value": self.normalized_value,
            "lean_identifier": self.lean_identifier,
        }


def assert_no_unknown_or_empty(value: str, *, field: str) -> str:
    """Reject empty strings and unknown placeholders in proof-relevant values."""
    if not isinstance(value, str) or not value.strip():
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"{field} must be a non-empty proof-relevant value",
            field_path=field,
        )
    if _FORBIDDEN_VALUE_RE.fullmatch(value.strip()) or _UNKNOWN_RE.search(value):
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"{field} must not use an unknown placeholder (got {value!r})",
            field_path=field,
        )
    return value


def require_sha256_digest(value: Any, *, field: str, artifact: str | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidProofInputDigest(
            f"{field} is missing or empty",
            field_path=field,
            artifact=artifact,
        )
    if not _DIGEST_RE.fullmatch(value):
        raise InvalidProofInputDigest(
            f"{field} must be sha256:<64 lowercase hex>, got {value!r}",
            field_path=field,
            artifact=artifact,
        )
    return value


def require_nonempty_id(value: Any, *, field: str, artifact: str | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObligationExtractionError(
            code="MissingCertificateId" if "certificate" in field else "MissingObligationId",
            message=f"{field} is required",
            field_path=field,
            artifact=artifact,
        )
    cleaned = value.strip()
    assert_no_unknown_or_empty(cleaned, field=field)
    return cleaned


def normalize_projected_value(raw: Any, *, field: str) -> str:
    """Declared normalization for projected JSON values (string form, strip, reject unknowns)."""
    if isinstance(raw, bool):
        text = "true" if raw else "false"
    elif isinstance(raw, int) and not isinstance(raw, bool):
        text = str(raw)
    elif isinstance(raw, str):
        text = raw.strip()
    elif raw is None:
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"{field}: JSON Pointer resolved to null",
            field_path=field,
        )
    else:
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"{field}: unsupported projected value type {type(raw).__name__}",
            field_path=field,
        )
    return assert_no_unknown_or_empty(text, field=field)


def synthetic_resolver_digest(*, resolver_id: str, resolver_version: str, normalized_value: str) -> str:
    """Digest binding a registered resolver identity to the concrete resolved value.

    A digest of release_id + namespace alone is intentionally insufficient.
    """
    require_sha256_digest(normalized_value, field=resolver_id, artifact=resolver_id)
    payload = (
        f"pcs-projection-resolver:{resolver_version}:{resolver_id}:{normalized_value}"
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def is_synthetic_artifact_path(artifact_path: str) -> bool:
    return artifact_path.startswith("#")


def lookup_synthetic_resolver(artifact_path: str) -> SyntheticResolverSpec:
    spec = SYNTHETIC_RESOLVER_REGISTRY.get(artifact_path)
    if spec is None:
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"unrecognized synthetic projection resolver: {artifact_path!r}",
            artifact=artifact_path,
        )
    return spec


def assert_path_contained(release_dir: Path, relative: str) -> Path:
    """Ensure ``relative`` resolves to a regular file under ``release_dir`` (no traversal)."""
    if not relative or relative.startswith("/") or relative.startswith("\\"):
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"artifact path must be release-relative, got {relative!r}",
            artifact=relative,
        )
    if ":" in relative.split("/")[0] and len(relative) >= 2 and relative[1] == ":":
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"artifact path must not be absolute, got {relative!r}",
            artifact=relative,
        )
    parts = Path(relative).parts
    if any(part == ".." for part in parts):
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"artifact path escapes release root: {relative!r}",
            artifact=relative,
        )
    root = release_dir.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"artifact path escapes release root: {relative!r}",
            artifact=relative,
        ) from exc
    if not candidate.is_file():
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"projection source artifact missing: {relative}",
            artifact=relative,
        )
    if candidate.is_symlink():
        # Symlink targets must still resolve under the release root (already checked via resolve).
        pass
    return candidate


def artifact_file_digest(release_dir: Path, relative: str) -> str:
    path = assert_path_contained(release_dir, relative)
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _load_json_artifact(release_dir: Path, relative: str) -> Any:
    path = assert_path_contained(release_dir, relative)
    return json.loads(path.read_text(encoding="utf-8"))


class ProjectionManifestBuilder:
    """Accumulate projection entries and emit PCSProjectionManifest.v0."""

    def __init__(
        self,
        *,
        release_dir: Path,
        release_id: str,
        workflow_id: str,
        projection_id: str | None = None,
    ) -> None:
        self.release_dir = release_dir.resolve()
        self.release_id = assert_no_unknown_or_empty(release_id, field="release_id")
        self.workflow_id = assert_no_unknown_or_empty(workflow_id, field="workflow_id")
        self.projection_id = projection_id or f"pcs-projection-{self.release_id}"
        self._entries: list[ProjectionEntry] = []
        self._digest_cache: dict[str, str] = {}
        self._lean_ids: dict[str, str] = {}
        self._pointer_keys: set[tuple[str, str]] = set()

    def _file_digest_for(self, artifact_path: str) -> str:
        if artifact_path not in self._digest_cache:
            self._digest_cache[artifact_path] = artifact_file_digest(
                self.release_dir,
                artifact_path,
            )
        return self._digest_cache[artifact_path]

    def _digest_for_entry(self, artifact_path: str, normalized_value: str) -> str:
        if is_synthetic_artifact_path(artifact_path):
            spec = lookup_synthetic_resolver(artifact_path)
            return synthetic_resolver_digest(
                resolver_id=spec.resolver_id,
                resolver_version=spec.version,
                normalized_value=normalized_value,
            )
        return self._file_digest_for(artifact_path)

    def add(
        self,
        *,
        artifact_path: str,
        json_pointer: str,
        normalized_value: str,
        lean_identifier: str,
        require_digest: bool = False,
    ) -> str:
        value = assert_no_unknown_or_empty(normalized_value, field=lean_identifier)
        if require_digest:
            value = require_sha256_digest(
                value,
                field=json_pointer,
                artifact=artifact_path,
            )
        if not json_pointer.startswith("/"):
            raise ObligationExtractionError(
                code="InvalidProofInputDigest",
                message=f"json_pointer must start with '/', got {json_pointer!r}",
                field_path=json_pointer,
                artifact=artifact_path,
            )
        assert_no_unknown_or_empty(lean_identifier, field="lean_identifier")
        if not _LEAN_IDENT_RE.fullmatch(lean_identifier):
            raise ObligationExtractionError(
                code="InvalidProofInputDigest",
                message=f"invalid lean_identifier {lean_identifier!r}",
                field_path=lean_identifier,
                artifact=artifact_path,
            )
        if is_synthetic_artifact_path(artifact_path):
            lookup_synthetic_resolver(artifact_path)
        else:
            assert_path_contained(self.release_dir, artifact_path)

        key = (artifact_path, json_pointer)
        if key in self._pointer_keys:
            raise ObligationExtractionError(
                code="InvalidProofInputDigest",
                message=(
                    f"duplicate projection entry for {artifact_path!r} pointer {json_pointer!r}"
                ),
                field_path=json_pointer,
                artifact=artifact_path,
            )
        prior = self._lean_ids.get(lean_identifier)
        if prior is not None:
            if prior != value:
                raise ObligationExtractionError(
                    code="InvalidProofInputDigest",
                    message=(
                        f"conflicting Lean identifier {lean_identifier!r}: "
                        f"{prior!r} vs {value!r}"
                    ),
                    field_path=lean_identifier,
                    artifact=artifact_path,
                )
            raise ObligationExtractionError(
                code="InvalidProofInputDigest",
                message=f"duplicate Lean identifier {lean_identifier!r}",
                field_path=lean_identifier,
                artifact=artifact_path,
            )

        entry = ProjectionEntry(
            artifact_path=artifact_path,
            artifact_digest=self._digest_for_entry(artifact_path, value),
            json_pointer=json_pointer,
            normalized_value=value,
            lean_identifier=lean_identifier,
        )
        self._pointer_keys.add(key)
        self._lean_ids[lean_identifier] = value
        self._entries.append(entry)
        return value

    def build(self) -> dict[str, Any]:
        if not self._entries:
            raise ObligationExtractionError(
                code="InvalidProofInputDigest",
                message="PCSProjectionManifest.v0 requires at least one entry",
            )
        body: dict[str, Any] = {
            "schema_version": "v0",
            "artifact_type": "PCSProjectionManifest.v0",
            "projection_id": self.projection_id,
            "release_id": self.release_id,
            "workflow_id": self.workflow_id,
            "entries": [entry.to_dict() for entry in self._entries],
            "signature_or_digest": PLACEHOLDER_DIGEST,
        }
        body["signature_or_digest"] = canonical_hash(body)
        return body


def projection_manifest_hash(manifest: dict[str, Any]) -> str:
    digest = manifest.get("signature_or_digest")
    if isinstance(digest, str) and _DIGEST_RE.fullmatch(digest):
        return digest
    return canonical_hash(manifest)


def recompute_projection_digest(manifest: dict[str, Any]) -> str:
    """Recompute the projection digest from the manifest body (excluding self-hash)."""
    return canonical_hash(manifest)


def validate_projection_manifest_structure(manifest: dict[str, Any]) -> list[str]:
    """Structural projection checks that do not require a release directory."""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["PCSProjectionManifest.v0 must be an object"]
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("PCSProjectionManifest.v0.entries must be a non-empty array")
        return errors

    lean_ids: dict[str, str] = {}
    pointer_keys: set[tuple[str, str]] = set()
    for index, entry in enumerate(entries):
        prefix = f"PCSProjectionManifest.v0.entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        artifact_path = entry.get("artifact_path")
        json_pointer = entry.get("json_pointer")
        normalized_value = entry.get("normalized_value")
        lean_identifier = entry.get("lean_identifier")
        artifact_digest = entry.get("artifact_digest")

        if not isinstance(artifact_path, str) or not artifact_path:
            errors.append(f"{prefix}.artifact_path must be a non-empty string")
            continue
        if not isinstance(json_pointer, str) or not json_pointer.startswith("/"):
            errors.append(f"{prefix}.json_pointer must start with '/'")
        if not isinstance(normalized_value, str) or not normalized_value.strip():
            errors.append(f"{prefix}.normalized_value must be non-empty")
        elif "unknown" in normalized_value.lower():
            errors.append(f"{prefix}.normalized_value must not contain an unknown placeholder")
        if not isinstance(lean_identifier, str) or not lean_identifier:
            errors.append(f"{prefix}.lean_identifier must be a non-empty string")
        elif not _LEAN_IDENT_RE.fullmatch(lean_identifier):
            errors.append(f"{prefix}.lean_identifier has invalid form")
        elif "unknown" in lean_identifier.lower():
            errors.append(f"{prefix}.lean_identifier must not contain an unknown placeholder")
        if isinstance(artifact_digest, str):
            if not _DIGEST_RE.fullmatch(artifact_digest):
                errors.append(f"{prefix}.artifact_digest must be sha256:<64 hex>")
        else:
            errors.append(f"{prefix}.artifact_digest must be a sha256 digest")

        if is_synthetic_artifact_path(artifact_path):
            if artifact_path not in SYNTHETIC_RESOLVER_REGISTRY:
                errors.append(
                    f"{prefix}: unrecognized synthetic projection resolver {artifact_path!r}",
                )
            elif isinstance(normalized_value, str) and _DIGEST_RE.fullmatch(normalized_value):
                spec = SYNTHETIC_RESOLVER_REGISTRY[artifact_path]
                expected = synthetic_resolver_digest(
                    resolver_id=spec.resolver_id,
                    resolver_version=spec.version,
                    normalized_value=normalized_value,
                )
                if artifact_digest != expected:
                    errors.append(
                        f"{prefix}.artifact_digest does not match resolver-bound digest",
                    )
        else:
            if ".." in Path(artifact_path).parts or artifact_path.startswith(("/", "\\")):
                errors.append(f"{prefix}.artifact_path escapes or is not release-relative")

        if isinstance(artifact_path, str) and isinstance(json_pointer, str):
            key = (artifact_path, json_pointer)
            if key in pointer_keys:
                errors.append(
                    f"{prefix}: duplicate entry for {artifact_path!r} pointer {json_pointer!r}",
                )
            pointer_keys.add(key)

        if isinstance(lean_identifier, str) and isinstance(normalized_value, str):
            prior = lean_ids.get(lean_identifier)
            if prior is not None:
                if prior != normalized_value:
                    errors.append(
                        f"{prefix}: conflicting Lean identifier {lean_identifier!r}",
                    )
                else:
                    errors.append(
                        f"{prefix}: duplicate Lean identifier {lean_identifier!r}",
                    )
            else:
                lean_ids[lean_identifier] = normalized_value

    declared = manifest.get("signature_or_digest")
    if isinstance(declared, str) and _DIGEST_RE.fullmatch(declared):
        recomputed = recompute_projection_digest(manifest)
        if declared != recomputed:
            errors.append(
                "PCSProjectionManifest.v0.signature_or_digest does not match recomputed digest",
            )
    return errors


def validate_projection_against_release(
    manifest: dict[str, Any],
    release_dir: Path,
    *,
    expected_hash: str | None = None,
) -> list[str]:
    """Full projection replay against a release root (B1 semantic validation)."""
    errors = validate_projection_manifest_structure(manifest)
    release_dir = release_dir.resolve()
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return errors

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        prefix = f"PCSProjectionManifest.v0.entries[{index}]"
        artifact_path = entry.get("artifact_path")
        json_pointer = entry.get("json_pointer")
        declared_value = entry.get("normalized_value")
        declared_digest = entry.get("artifact_digest")
        lean_identifier = entry.get("lean_identifier")
        if not isinstance(artifact_path, str) or not isinstance(json_pointer, str):
            continue
        if not isinstance(declared_value, str) or not isinstance(lean_identifier, str):
            continue

        try:
            if is_synthetic_artifact_path(artifact_path):
                spec = lookup_synthetic_resolver(artifact_path)
                resolved = normalize_projected_value(
                    spec.resolve(release_dir),
                    field=lean_identifier,
                )
                expected_digest = synthetic_resolver_digest(
                    resolver_id=spec.resolver_id,
                    resolver_version=spec.version,
                    normalized_value=resolved,
                )
            else:
                recomputed_digest = artifact_file_digest(release_dir, artifact_path)
                if declared_digest != recomputed_digest:
                    errors.append(
                        f"{prefix}.artifact_digest mismatch for {artifact_path!r}",
                    )
                if json_pointer == PAYLOAD_SHA256_POINTER:
                    # B3: entry binds the payload file digest itself (not a JSON field).
                    # Reject symlink / reparse escapes the same way as ResultArtifact verification.
                    from pcs_core.safe_paths import UnsafePathError, resolve_contained_file

                    try:
                        resolve_contained_file(release_dir, artifact_path)
                    except UnsafePathError as exc:
                        errors.append(
                            f"{prefix}: unsafe payload path {artifact_path!r}: {exc}",
                        )
                        continue
                    resolved = normalize_projected_value(
                        recomputed_digest,
                        field=lean_identifier,
                    )
                    if declared_value != recomputed_digest:
                        errors.append(
                            f"{prefix}.normalized_value must equal payload file digest "
                            f"for {PAYLOAD_SHA256_POINTER}",
                        )
                    expected_digest = recomputed_digest
                else:
                    doc = _load_json_artifact(release_dir, artifact_path)
                    try:
                        raw = resolve_pointer(doc, json_pointer)
                    except (JsonPointerException, KeyError, TypeError, ValueError) as exc:
                        errors.append(
                            f"{prefix}: failed to resolve JSON Pointer {json_pointer!r}: {exc}",
                        )
                        continue
                    resolved = normalize_projected_value(raw, field=lean_identifier)
                    expected_digest = recomputed_digest

            if resolved != declared_value:
                errors.append(
                    f"{prefix}.normalized_value mismatch: declared {declared_value!r} "
                    f"!= resolved {resolved!r}",
                )
            if declared_digest != expected_digest:
                errors.append(
                    f"{prefix}.artifact_digest does not match recomputed digest",
                )
        except ObligationExtractionError as exc:
            errors.append(f"{prefix}: {exc}")

    if expected_hash is not None:
        try:
            require_sha256_digest(expected_hash, field="pcs_projection_manifest_hash")
            actual = projection_manifest_hash(manifest)
            if actual != expected_hash:
                errors.append(
                    "pcs_projection_manifest_hash does not match projection digest",
                )
        except ObligationExtractionError as exc:
            errors.append(str(exc))

    return errors


def validate_proof_obligation_projection(
    data: dict[str, Any],
    *,
    release_dir: Path | None = None,
) -> list[str]:
    """Validate mandatory PCS projection fields on ProofObligation.v0."""
    errors: list[str] = []
    manifest = data.get("pcs_projection_manifest")
    proj_hash = data.get("pcs_projection_manifest_hash")
    if not isinstance(manifest, dict):
        errors.append("ProofObligation.v0 requires pcs_projection_manifest")
        return errors
    if not isinstance(proj_hash, str) or not _DIGEST_RE.fullmatch(proj_hash):
        errors.append(
            "ProofObligation.v0 requires pcs_projection_manifest_hash as sha256 digest",
        )

    release_id = data.get("release_id")
    workflow_id = data.get("workflow_id")
    if isinstance(release_id, str) and manifest.get("release_id") != release_id:
        errors.append("pcs_projection_manifest.release_id must match ProofObligation.release_id")
    if isinstance(workflow_id, str) and manifest.get("workflow_id") != workflow_id:
        errors.append(
            "pcs_projection_manifest.workflow_id must match ProofObligation.workflow_id",
        )

    if release_dir is not None:
        errors.extend(
            validate_projection_against_release(
                manifest,
                release_dir,
                expected_hash=proj_hash if isinstance(proj_hash, str) else None,
            ),
        )
    else:
        errors.extend(validate_projection_manifest_structure(manifest))
        if isinstance(proj_hash, str) and _DIGEST_RE.fullmatch(proj_hash):
            if projection_manifest_hash(manifest) != proj_hash:
                errors.append(
                    "pcs_projection_manifest_hash does not match projection digest",
                )
    return errors
