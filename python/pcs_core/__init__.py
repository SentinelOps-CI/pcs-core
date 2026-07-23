"""Proof-Carrying Science (PCS) core validation library."""

from pcs_core.conformance import (
    LABTRUST_INVALID_FIXTURES,
    LABTRUST_VALID_FIXTURES,
    labtrust_examples_dir,
    labtrust_fixture_path,
)
from pcs_core.hash import (
    CANONICALIZATION_VERSION,
    canonical_hash,
    canonical_json_bytes,
    canonicalize_for_hash,
    domain_separated_signing_message,
)
from pcs_core.status import (
    ARTIFACT_STATUSES,
    TRACE_CERTIFICATE_STATUSES,
    ArtifactStatus,
    is_valid_status,
)
from pcs_core.validate import (
    DetectionMode,
    detect_artifact_type,
    validate_artifact,
    validate_file,
)

__all__ = [
    "LABTRUST_INVALID_FIXTURES",
    "LABTRUST_VALID_FIXTURES",
    "ARTIFACT_STATUSES",
    "CANONICALIZATION_VERSION",
    "TRACE_CERTIFICATE_STATUSES",
    "ArtifactStatus",
    "DetectionMode",
    "canonical_hash",
    "canonical_json_bytes",
    "canonicalize_for_hash",
    "detect_artifact_type",
    "domain_separated_signing_message",
    "is_valid_status",
    "labtrust_examples_dir",
    "labtrust_fixture_path",
    "validate_artifact",
    "validate_file",
]

__version__ = "0.1.0"
