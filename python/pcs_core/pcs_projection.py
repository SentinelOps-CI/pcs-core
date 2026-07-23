"""PCSProjectionManifest.v0: bind extracted proof fields to artifact digests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.obligation_extraction_errors import (
    InvalidProofInputDigest,
    ObligationExtractionError,
)
from pcs_core.release_fixtures import file_digest

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_UNKNOWN_RE = re.compile(r"(?i)(^|[^a-z0-9])unknown([^a-z0-9]|$)")
_FORBIDDEN_VALUE_RE = re.compile(
    r"(?i)^(cert-unknown|release-unknown|proof-obligation-unknown|witness-unknown|unknown)$"
)


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


def artifact_file_digest(release_dir: Path, relative: str) -> str:
    path = release_dir / relative
    if not path.is_file():
        raise ObligationExtractionError(
            code="InvalidProofInputDigest",
            message=f"projection source artifact missing: {relative}",
            artifact=relative,
        )
    return file_digest(path.read_bytes())


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

    def _digest_for(self, artifact_path: str) -> str:
        if artifact_path not in self._digest_cache:
            if artifact_path.startswith("#"):
                # Synthetic resolver source — hash the release_id + pointer namespace.
                synthetic = f"synthetic:{self.release_id}:{artifact_path}".encode("utf-8")
                from hashlib import sha256

                self._digest_cache[artifact_path] = f"sha256:{sha256(synthetic).hexdigest()}"
            else:
                self._digest_cache[artifact_path] = artifact_file_digest(
                    self.release_dir,
                    artifact_path,
                )
        return self._digest_cache[artifact_path]

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
        entry = ProjectionEntry(
            artifact_path=artifact_path,
            artifact_digest=self._digest_for(artifact_path),
            json_pointer=json_pointer,
            normalized_value=value,
            lean_identifier=lean_identifier,
        )
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
