"""Paths to canonical cross-repo conformance fixtures (LabTrust v0.1 flow)."""

from __future__ import annotations

from pathlib import Path

from pcs_core.paths import examples_dir

LABTRUST_VALID_FIXTURES: tuple[str, ...] = (
    "science_claim_bundle.pending.valid.json",
    "trace_certificate.valid.json",
    "science_claim_bundle.certified.valid.json",
    "verification_result.valid.json",
    "signed_science_claim_bundle.valid.json",
)

LABTRUST_INVALID_FIXTURES: tuple[str, ...] = (
    "invalid_signed_schema_version_artifact_name.json",
    "invalid_singular_runtime_receipt_bundle.json",
)


def labtrust_examples_dir() -> Path:
    return examples_dir() / "labtrust"


def labtrust_fixture_path(name: str) -> Path:
    path = labtrust_examples_dir() / name
    if not path.is_file():
        raise FileNotFoundError(f"LabTrust conformance fixture not found: {path}")
    return path
