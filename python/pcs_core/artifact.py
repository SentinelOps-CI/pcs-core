"""Artifact type detection and schema mapping."""

from __future__ import annotations

from pathlib import Path

ARTIFACT_SCHEMAS: dict[str, str] = {
    "AssumptionSet.v0": "AssumptionSet.v0.schema.json",
    "SourceSpan.v0": "SourceSpan.v0.schema.json",
    "ClaimArtifact.v0": "ClaimArtifact.v0.schema.json",
    "RuntimeReceipt.v0": "RuntimeReceipt.v0.schema.json",
    "TraceCertificate.v0": "TraceCertificate.v0.schema.json",
    "EvidenceBundle.v0": "EvidenceBundle.v0.schema.json",
    "ScienceClaimBundle.v0": "ScienceClaimBundle.v0.schema.json",
    "VerificationResult.v0": "VerificationResult.v0.schema.json",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def schemas_dir() -> Path:
    return repo_root() / "schemas"


def detect_artifact_type(data: dict) -> str | None:
    if "bundle_id" in data and "claim_artifact" in data:
        return "ScienceClaimBundle.v0"
    if "verification_id" in data:
        return "VerificationResult.v0"
    if "receipt_id" in data:
        return "RuntimeReceipt.v0"
    if "certificate_id" in data:
        return "TraceCertificate.v0"
    if "assumption_set_id" in data:
        return "AssumptionSet.v0"
    if "source_span_id" in data:
        return "SourceSpan.v0"
    if data.get("artifact_type") == "ClaimArtifact.v0":
        return "ClaimArtifact.v0"
    if "bundle_id" in data and "claim_refs" in data:
        return "EvidenceBundle.v0"
    return None
