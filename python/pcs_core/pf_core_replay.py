"""Deterministic PF-Core trace replay validation."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from pcs_core.hash import canonical_hash
from pcs_core.pf_core_runtime import (
    GENESIS_HASH,
    compile_runtime_observation_to_event,
    compile_tool_use_trace_to_pfcore_trace,
    compute_event_hash,
    compute_trace_hash,
    normalize_hash,
)
from pcs_core.validate import detect_artifact_type, validate_schema

REPLAY_DISCLAIMER = (
    "PF-Core replay-trace recomputes event and trace hashes deterministically and "
    "compares them to the stored PFCoreTrace.v0. When --source is provided, the "
    "compiler is re-run from ToolUseTrace.v0 or PFCoreRuntimeObservation.v0. "
    "ReplayValidated is emitted only when hashes and compiled content match. "
    "Replay certificates cannot upgrade claim_class above the source trace."
)

# Monotonic assurance ordering for trace/certificate claim classes (low → high).
_CLAIM_CLASS_RANK: dict[str, int] = {
    "OutOfScope": 0,
    "SchemaValidated": 1,
    "RuntimeChecked": 2,
    "ReplayValidated": 3,
    "AssumptionDeclared": 4,
    "CertificateChecked": 5,
    "LeanKernelChecked": 6,
}


def claim_class_rank(claim_class: str) -> int | None:
    """Return monotonic rank for a PF-Core claim class, or None when unknown."""
    return _CLAIM_CLASS_RANK.get(str(claim_class or ""))


def replay_preserves_claim_boundary(source_claim_class: str, replay_claim_class: str) -> bool:
    """ReplayValidated certificates must not exceed the source trace claim class rank.

    **Meaning:** Hash replay match does not silently upgrade assurance beyond what the
    source trace already claimed.

    **Trusted use:** ``build_replay_certificate`` and replay integration tests.

    **Does not imply:** Lean kernel proof, contract discharge, or non-replay assurance.
    """
    source_rank = claim_class_rank(source_claim_class)
    replay_rank = claim_class_rank(replay_claim_class)
    if source_rank is None or replay_rank is None:
        return False
    return replay_rank <= source_rank


_HASH_COMPARE_KEYS = frozenset({"trace_hash", "event_hash", "signature_or_digest"})


@dataclass(frozen=True)
class ReplayDiff:
    path: str
    expected: Any
    actual: Any


@dataclass
class ReplayResult:
    match: bool
    original_trace_hash: str
    recomputed_trace_hash: str
    diffs: list[ReplayDiff] = field(default_factory=list)
    error: str | None = None
    recomputed_trace: dict[str, Any] | None = None


def recompute_pfcore_trace_hashes(trace: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with event_hash and trace_hash recomputed deterministically."""
    result: dict[str, Any] = json.loads(json.dumps(trace))
    events = result.get("events")
    if not isinstance(events, list):
        return result

    previous = normalize_hash(GENESIS_HASH)
    for event in events:
        if not isinstance(event, dict):
            continue
        event["previous_event_hash"] = previous
        event_hash = compute_event_hash(event)
        event["event_hash"] = event_hash
        event["signature_or_digest"] = event_hash
        previous = event_hash

    trace_hash = compute_trace_hash(result)
    result["trace_hash"] = trace_hash
    result["signature_or_digest"] = trace_hash
    return result


def _compare_hash_chain(
    original: Mapping[str, Any],
    recomputed: Mapping[str, Any],
) -> list[ReplayDiff]:
    diffs: list[ReplayDiff] = []
    orig_hash = str(original.get("trace_hash") or "")
    new_hash = str(recomputed.get("trace_hash") or "")
    if orig_hash != new_hash:
        diffs.append(ReplayDiff("trace_hash", orig_hash, new_hash))

    orig_events = original.get("events")
    new_events = recomputed.get("events")
    if not isinstance(orig_events, list) or not isinstance(new_events, list):
        return diffs
    if len(orig_events) != len(new_events):
        diffs.append(ReplayDiff("events.length", len(orig_events), len(new_events)))
        return diffs

    for index, (orig_event, new_event) in enumerate(zip(orig_events, new_events, strict=False)):
        if not isinstance(orig_event, dict) or not isinstance(new_event, dict):
            continue
        for key in ("event_hash", "previous_event_hash", "signature_or_digest"):
            if orig_event.get(key) != new_event.get(key):
                diffs.append(
                    ReplayDiff(
                        f"events[{index}].{key}",
                        orig_event.get(key),
                        new_event.get(key),
                    )
                )
    return diffs


def _compare_traces(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
) -> list[ReplayDiff]:
    diffs = _compare_hash_chain(expected, actual)
    for key in ("trace_id", "workflow_id", "policy_hash", "contract_hash", "claim_class"):
        if expected.get(key) != actual.get(key):
            diffs.append(ReplayDiff(key, expected.get(key), actual.get(key)))

    expected_events = expected.get("events")
    actual_events = actual.get("events")
    if not isinstance(expected_events, list) or not isinstance(actual_events, list):
        return diffs
    for index, (exp_event, act_event) in enumerate(
        zip(expected_events, actual_events, strict=False)
    ):
        if not isinstance(exp_event, dict) or not isinstance(act_event, dict):
            continue
        for key in sorted(set(exp_event) | set(act_event)):
            if key in _HASH_COMPARE_KEYS:
                continue
            if exp_event.get(key) != act_event.get(key):
                diffs.append(
                    ReplayDiff(
                        f"events[{index}].{key}",
                        exp_event.get(key),
                        act_event.get(key),
                    )
                )
    return diffs


def compile_observation_to_pfcore_trace(observation: dict) -> dict:
    """Compile a single PFCoreRuntimeObservation.v0 into a one-event PFCoreTrace.v0."""
    event = compile_runtime_observation_to_event(observation)
    trace: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreTrace.v0",
        "trace_id": str(observation["trace_id"]),
        "workflow_id": str(observation.get("runtime_ref") or "observation.single"),
        "events": [event],
        "trace_hash": GENESIS_HASH,
        "policy_hash": GENESIS_HASH,
        "contract_hash": GENESIS_HASH,
        "claim_class": "RuntimeChecked",
        "source_repo": str(observation["source_repo"]),
        "source_commit": str(observation["source_commit"]),
        "signature_or_digest": GENESIS_HASH,
    }
    trace["trace_hash"] = compute_trace_hash(trace)
    trace["signature_or_digest"] = trace["trace_hash"]
    return trace


def compile_source_to_pfcore_trace(source: Mapping[str, Any]) -> dict:
    artifact_type = detect_artifact_type(dict(source))
    if artifact_type == "ToolUseTrace.v0":
        return compile_tool_use_trace_to_pfcore_trace(dict(source))
    if artifact_type == "PFCoreRuntimeObservation.v0":
        return compile_observation_to_pfcore_trace(dict(source))
    raise ValueError(
        f"unsupported replay source artifact type {artifact_type!r}; "
        "expected ToolUseTrace.v0 or PFCoreRuntimeObservation.v0"
    )


def replay_trace(trace_path: Path, source_path: Path | None = None) -> ReplayResult:
    """Replay a PFCoreTrace.v0, optionally recompiling from source."""
    original = json.loads(trace_path.read_text(encoding="utf-8"))
    schema_errors = validate_schema(original, "PFCoreTrace.v0")
    if schema_errors:
        return ReplayResult(
            match=False,
            original_trace_hash=str(original.get("trace_hash") or ""),
            recomputed_trace_hash="",
            error=f"schema invalid: {'; '.join(schema_errors)}",
        )

    original_hash = str(original.get("trace_hash") or "")

    try:
        if source_path is not None:
            source = json.loads(source_path.read_text(encoding="utf-8"))
            recomputed = compile_source_to_pfcore_trace(source)
            diffs = _compare_traces(original, recomputed)
        else:
            recomputed = recompute_pfcore_trace_hashes(original)
            diffs = _compare_hash_chain(original, recomputed)
    except Exception as exc:
        return ReplayResult(
            match=False,
            original_trace_hash=original_hash,
            recomputed_trace_hash="",
            error=str(exc),
        )

    recomputed_hash = str(recomputed.get("trace_hash") or "")
    match = not diffs and original_hash == recomputed_hash
    return ReplayResult(
        match=match,
        original_trace_hash=original_hash,
        recomputed_trace_hash=recomputed_hash,
        diffs=diffs,
        recomputed_trace=recomputed,
    )


def build_replay_certificate(trace: Mapping[str, Any], result: ReplayResult) -> dict[str, Any]:
    events = trace.get("events")
    event_count = len(events) if isinstance(events, list) else 0
    source_claim = str(trace.get("claim_class") or "RuntimeChecked")
    replay_claim = source_claim if result.match else "OutOfScope"
    if result.match and not replay_preserves_claim_boundary(source_claim, replay_claim):
        replay_claim = "OutOfScope"
    cert: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreCertificate.v0",
        "certificate_id": f"pfcore-replay-{trace.get('trace_id', 'unknown')}",
        "trace_hash": result.original_trace_hash,
        "contract_hash": str(trace.get("contract_hash") or GENESIS_HASH),
        "policy_hash": str(trace.get("policy_hash") or GENESIS_HASH),
        "claim_class": replay_claim,
        "checker": "pcs-core",
        "checker_version": "0.1.0",
        "assumption_refs": [
            "docs/pf-core/assumptions.md",
            "docs/pf-core/trusted-boundary.md",
        ],
        "obligations": [
            {
                "kind": "TraceReplay",
                "theorem": "trace_hash_replay",
                "passed": result.match,
            },
            {
                "kind": "ReplayClaimBoundary",
                "theorem": "replay_preserves_claim_boundary",
                "passed": replay_preserves_claim_boundary(source_claim, replay_claim),
            },
        ],
        "replay_match": result.match,
        "original_trace_hash": result.original_trace_hash,
        "recomputed_trace_hash": result.recomputed_trace_hash,
        "disclaimer": REPLAY_DISCLAIMER,
        "event_count": event_count,
        "source_repo": str(trace.get("source_repo") or "https://github.com/example/pcs-core"),
        "source_commit": str(trace.get("source_commit") or "0000000"),
        "signature_or_digest": GENESIS_HASH,
    }
    cert["signature_or_digest"] = canonical_hash(cert)
    return cert


def build_replay_check_result(
    trace_path: Path,
    result: ReplayResult,
    *,
    certificate: dict[str, Any] | None = None,
    source_trace: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_claim = str((source_trace or {}).get("claim_class") or "RuntimeChecked")
    if certificate is not None:
        claim_class = str(certificate.get("claim_class") or "OutOfScope")
    elif result.match:
        claim_class = source_claim
    else:
        claim_class = "OutOfScope"
    status = "ReplayValidated" if result.match else "Rejected"
    replay_boundary_passed = replay_preserves_claim_boundary(source_claim, claim_class)
    issues: list[dict[str, Any]] = []
    if result.error:
        issues.append({"code": "ReplayError", "message": result.error})
    for diff in result.diffs:
        issues.append(
            {
                "code": "ReplayMismatch",
                "message": f"{diff.path}: expected {diff.expected!r}, got {diff.actual!r}",
                "path": diff.path,
            }
        )

    payload: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "LeanCheckResult.v0",
        "status": status,
        "claim_class": claim_class,
        "trace_path": str(trace_path),
        "issues": issues,
        "obligations": [
            {
                "kind": "ReplayClaimBoundary",
                "theorem": "replay_preserves_claim_boundary",
                "passed": replay_boundary_passed,
            }
        ],
        "assumption_refs": [
            "docs/pf-core/assumptions.md",
            "docs/pf-core/trusted-boundary.md",
        ],
        "theorems_checked": ["trace_hash_replay", "replay_preserves_claim_boundary"],
        "lean_build_status": {"ok": False, "target": "PFCore", "detail": "not-applicable"},
        "lean_proof_checked": False,
        "replay_match": result.match,
        "original_trace_hash": result.original_trace_hash,
        "recomputed_trace_hash": result.recomputed_trace_hash,
        "disclaimer": REPLAY_DISCLAIMER,
        "certificate": certificate,
        "signature_or_digest": GENESIS_HASH,
    }
    payload["signature_or_digest"] = canonical_hash(payload)
    return payload


def run_replay_trace(
    trace_path: Path,
    *,
    source_path: Path | None = None,
    out_path: Path | None = None,
    result_out_path: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    """Run replay validation and optionally write certificate / result artifacts."""
    original = json.loads(trace_path.read_text(encoding="utf-8"))
    result = replay_trace(trace_path, source_path)

    certificate: dict[str, Any] | None = None
    if result.match:
        certificate = build_replay_certificate(original, result)
        cert_errors = validate_schema(certificate, "PFCoreCertificate.v0")
        if cert_errors:
            result = ReplayResult(
                match=False,
                original_trace_hash=result.original_trace_hash,
                recomputed_trace_hash=result.recomputed_trace_hash,
                diffs=result.diffs,
                error=f"certificate schema invalid: {'; '.join(cert_errors)}",
            )
            certificate = None

    check_result = build_replay_check_result(
        trace_path, result, certificate=certificate, source_trace=original
    )

    if result_out_path:
        result_out_path.write_text(json.dumps(check_result, indent=2), encoding="utf-8")
    if out_path and certificate is not None:
        out_path.write_text(json.dumps(certificate, indent=2), encoding="utf-8")

    return (0 if result.match else 1), check_result


def print_replay_disclaimer(*, stream=None) -> None:
    stream = stream or sys.stderr
    print(REPLAY_DISCLAIMER, file=stream)
