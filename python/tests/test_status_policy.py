"""PCS status transition policy."""

import pytest

from pcs_core.status import ArtifactStatus
from pcs_core.status_policy import check_status_transition, explain_status


def test_explain_proof_checked() -> None:
    text = explain_status(ArtifactStatus.PROOF_CHECKED.value)
    assert "Provability Fabric" in text
    assert "Stale" in text


def test_allowed_runtime_to_certificate_pending() -> None:
    verdict = check_status_transition(
        ArtifactStatus.RUNTIME_OBSERVED.value,
        ArtifactStatus.CERTIFICATE_PENDING.value,
    )
    assert verdict.allowed


def test_forbidden_rejected_to_proof_checked() -> None:
    verdict = check_status_transition(
        ArtifactStatus.REJECTED.value,
        ArtifactStatus.PROOF_CHECKED.value,
    )
    assert not verdict.allowed
    assert "forbidden" in verdict.message


def test_terminal_stale_cannot_advance() -> None:
    verdict = check_status_transition(
        ArtifactStatus.STALE.value,
        ArtifactStatus.CERTIFICATE_CHECKED.value,
    )
    assert not verdict.allowed


def test_unchanged_status_allowed() -> None:
    verdict = check_status_transition(
        ArtifactStatus.PROOF_CHECKED.value,
        ArtifactStatus.PROOF_CHECKED.value,
    )
    assert verdict.allowed


@pytest.mark.parametrize(
    ("old_status", "new_status"),
    [
        (ArtifactStatus.DRAFT.value, ArtifactStatus.PROOF_CHECKED.value),
        (ArtifactStatus.RUNTIME_OBSERVED.value, ArtifactStatus.PROOF_CHECKED.value),
    ],
)
def test_forbidden_skip_ahead(old_status: str, new_status: str) -> None:
    verdict = check_status_transition(old_status, new_status)
    assert not verdict.allowed
