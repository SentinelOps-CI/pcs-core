"""Canonical PCS artifact status enum."""

from enum import Enum


class ArtifactStatus(str, Enum):
    DRAFT = "Draft"
    EXTRACTED = "Extracted"
    HUMAN_REVIEWED = "HumanReviewed"
    FORMALIZED = "Formalized"
    PROOF_PENDING = "ProofPending"
    PROOF_CHECKED = "ProofChecked"
    CERTIFICATE_PENDING = "CertificatePending"
    CERTIFICATE_CHECKED = "CertificateChecked"
    RUNTIME_OBSERVED = "RuntimeObserved"
    RUNTIME_CHECKED = "RuntimeChecked"
    REJECTED = "Rejected"
    EMPIRICAL_ONLY = "EmpiricalOnly"
    DEPRECATED = "Deprecated"
    STALE = "Stale"


ARTIFACT_STATUSES: frozenset[str] = frozenset(s.value for s in ArtifactStatus)

TRACE_CERTIFICATE_STATUSES: frozenset[str] = frozenset(
    {
        ArtifactStatus.CERTIFICATE_PENDING.value,
        ArtifactStatus.CERTIFICATE_CHECKED.value,
        ArtifactStatus.REJECTED.value,
        ArtifactStatus.STALE.value,
    }
)

CHECK_STATUSES: frozenset[str] = frozenset({"passed", "failed", "skipped", "warning"})


def is_valid_status(value: str) -> bool:
    return value in ARTIFACT_STATUSES
