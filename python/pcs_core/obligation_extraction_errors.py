"""Typed fail-closed errors for PCS proof-obligation extraction and Lean codegen.

Proof-relevant identifiers and digests must never be invented. Missing or malformed
values raise a typed error instead of falling back to placeholders such as
``cert-unknown``, ``release-unknown``, or empty hashes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObligationExtractionError(ValueError):
    """Base class for fail-closed obligation extraction failures."""

    code: str
    message: str
    field_path: str | None = None
    artifact: str | None = None

    def __str__(self) -> str:
        parts = [f"{self.code}: {self.message}"]
        if self.artifact:
            parts.append(f"artifact={self.artifact}")
        if self.field_path:
            parts.append(f"path={self.field_path}")
        return " ".join(parts)


class MissingCertificateId(ObligationExtractionError):
    def __init__(
        self,
        message: str = "certificate_id is required",
        *,
        field_path: str | None = "/certificate_id",
        artifact: str | None = None,
    ) -> None:
        super().__init__(
            code="MissingCertificateId",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )


class MissingTraceHash(ObligationExtractionError):
    def __init__(
        self,
        message: str = "trace_hash is required",
        *,
        field_path: str | None = "/trace_hash",
        artifact: str | None = None,
    ) -> None:
        super().__init__(
            code="MissingTraceHash",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )


class MissingCertifiedBundleHash(ObligationExtractionError):
    def __init__(
        self,
        message: str = "certified_bundle_hash is required",
        *,
        field_path: str | None = None,
        artifact: str | None = None,
    ) -> None:
        super().__init__(
            code="MissingCertifiedBundleHash",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )


class MissingVerificationChecks(ObligationExtractionError):
    def __init__(
        self,
        message: str = "verification_result.checks is required and must be non-empty",
        *,
        field_path: str | None = "/checks",
        artifact: str | None = "verification_result.json",
    ) -> None:
        super().__init__(
            code="MissingVerificationChecks",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )


class InvalidProofInputDigest(ObligationExtractionError):
    def __init__(
        self,
        message: str = "proof-relevant digest must be sha256:<64 lowercase hex>",
        *,
        field_path: str | None = None,
        artifact: str | None = None,
    ) -> None:
        super().__init__(
            code="InvalidProofInputDigest",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )


class MissingReleaseId(ObligationExtractionError):
    def __init__(
        self,
        message: str = "release_id is required",
        *,
        field_path: str | None = "/release_id",
        artifact: str | None = "release_manifest.v0.json",
    ) -> None:
        super().__init__(
            code="MissingReleaseId",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )


class MissingObligationId(ObligationExtractionError):
    def __init__(
        self,
        message: str = "obligation_id is required",
        *,
        field_path: str | None = "/obligation_id",
        artifact: str | None = None,
    ) -> None:
        super().__init__(
            code="MissingObligationId",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )


class MissingWitnessId(ObligationExtractionError):
    def __init__(
        self,
        message: str = "witness_id is required",
        *,
        field_path: str | None = "/witness_id",
        artifact: str | None = "computation_witness.json",
    ) -> None:
        super().__init__(
            code="MissingWitnessId",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )


class MissingArtifactStatus(ObligationExtractionError):
    def __init__(
        self,
        message: str = "artifact status is required",
        *,
        field_path: str | None = "/status",
        artifact: str | None = None,
    ) -> None:
        super().__init__(
            code="MissingArtifactStatus",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )


class MissingPolicyHash(ObligationExtractionError):
    def __init__(
        self,
        message: str = "policy_hash is required",
        *,
        field_path: str | None = "/policy_hash",
        artifact: str | None = None,
    ) -> None:
        super().__init__(
            code="MissingPolicyHash",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )


class MissingVerifiedBundleHash(ObligationExtractionError):
    def __init__(
        self,
        message: str = "verified_input.bundle_hash is required",
        *,
        field_path: str | None = "/verified_input/bundle_hash",
        artifact: str | None = "verification_result.json",
    ) -> None:
        super().__init__(
            code="MissingVerifiedBundleHash",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )


class MissingSignedBundleHash(ObligationExtractionError):
    def __init__(
        self,
        message: str = "signed_input_bundle_hash is required",
        *,
        field_path: str | None = "/signed_input_bundle_hash",
        artifact: str | None = "signed_science_claim_bundle.json",
    ) -> None:
        super().__init__(
            code="MissingSignedBundleHash",
            message=message,
            field_path=field_path,
            artifact=artifact,
        )
