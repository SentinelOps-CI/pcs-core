"""PCS status transition policy (v0.1)."""

from __future__ import annotations

from dataclasses import dataclass

from pcs_core.status import ArtifactStatus

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    ArtifactStatus.DRAFT.value: frozenset({ArtifactStatus.RUNTIME_OBSERVED.value}),
    ArtifactStatus.RUNTIME_OBSERVED.value: frozenset(
        {ArtifactStatus.CERTIFICATE_PENDING.value, ArtifactStatus.CERTIFICATE_CHECKED.value},
    ),
    ArtifactStatus.CERTIFICATE_PENDING.value: frozenset(
        {ArtifactStatus.CERTIFICATE_CHECKED.value, ArtifactStatus.REJECTED.value},
    ),
    ArtifactStatus.CERTIFICATE_CHECKED.value: frozenset({ArtifactStatus.PROOF_CHECKED.value}),
    ArtifactStatus.PROOF_CHECKED.value: frozenset({ArtifactStatus.STALE.value}),
    ArtifactStatus.REJECTED.value: frozenset(),
    ArtifactStatus.STALE.value: frozenset(),
    ArtifactStatus.DEPRECATED.value: frozenset(),
}

FORBIDDEN_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (ArtifactStatus.REJECTED.value, ArtifactStatus.PROOF_CHECKED.value),
        (ArtifactStatus.STALE.value, ArtifactStatus.PROOF_CHECKED.value),
        (ArtifactStatus.DEPRECATED.value, ArtifactStatus.PROOF_CHECKED.value),
        (ArtifactStatus.DRAFT.value, ArtifactStatus.PROOF_CHECKED.value),
        (ArtifactStatus.RUNTIME_OBSERVED.value, ArtifactStatus.PROOF_CHECKED.value),
    },
)

STATUS_DESCRIPTIONS: dict[str, str] = {
    ArtifactStatus.DRAFT.value: "Initial authoring; not yet tied to runtime evidence.",
    ArtifactStatus.RUNTIME_OBSERVED.value: "Runtime evidence captured in a receipt or trace.",
    ArtifactStatus.CERTIFICATE_PENDING.value: "Awaiting CertifyEdge trace certificate attachment.",
    ArtifactStatus.CERTIFICATE_CHECKED.value: "Trace certificate attached and checked.",
    ArtifactStatus.PROOF_CHECKED.value: "Provability Fabric verification succeeded.",
    ArtifactStatus.REJECTED.value: "Terminal failure; regenerate artifacts to continue.",
    ArtifactStatus.STALE.value: "Terminal staleness; refresh evidence before reuse.",
    ArtifactStatus.DEPRECATED.value: "Terminal deprecation; migrate schema before reuse.",
}


@dataclass(frozen=True)
class TransitionVerdict:
    allowed: bool
    message: str


def explain_status(status: str) -> str:
    if status not in STATUS_DESCRIPTIONS:
        return f"Unknown PCS status: {status}"
    allowed_next = sorted(ALLOWED_TRANSITIONS.get(status, frozenset()))
    lines = [STATUS_DESCRIPTIONS[status], f"Allowed next: {', '.join(allowed_next) or '(none)'}"]
    return "\n".join(lines)


def check_status_transition(old_status: str, new_status: str) -> TransitionVerdict:
    if old_status == new_status:
        return TransitionVerdict(True, f"unchanged status {old_status!r}")
    if (old_status, new_status) in FORBIDDEN_TRANSITIONS:
        return TransitionVerdict(
            False,
            f"forbidden transition {old_status!r} -> {new_status!r} "
            "(regenerate or refresh required)",
        )
    allowed = ALLOWED_TRANSITIONS.get(old_status, frozenset())
    if new_status in allowed:
        return TransitionVerdict(True, f"allowed transition {old_status!r} -> {new_status!r}")
    if not allowed and old_status in {
        ArtifactStatus.REJECTED.value,
        ArtifactStatus.STALE.value,
        ArtifactStatus.DEPRECATED.value,
    }:
        return TransitionVerdict(
            False,
            f"terminal status {old_status!r} cannot transition to {new_status!r}",
        )
    return TransitionVerdict(
        False,
        f"transition {old_status!r} -> {new_status!r} not in policy "
        f"(allowed: {', '.join(sorted(allowed)) or 'none'})",
    )
