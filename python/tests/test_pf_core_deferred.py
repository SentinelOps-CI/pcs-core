"""Tests for deferred PF-Core execution plan items."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.hash import canonical_hash, canonicalize_for_hash
from pcs_core.pf_core_contract import (
    DEFAULT_TRACE_SAFE_CONTRACT_ID,
    trace_has_contract_binding,
)
from pcs_core.pf_core_runtime import (
    DroppedDeniedEvent,
    compile_runtime_observation_to_event,
    compile_runtime_observations_to_pfcore_trace,
    compute_event_hash,
    compute_trace_hash,
    validate_denied_observations_preserved,
)
from pcs_core.validate import (
    ValidationError,
    check_pf_core_invalid_fixtures,
    load_pf_core_fixture_manifest,
    validate_semantics,
)

REPO = Path(__file__).resolve().parents[2]
VALID = REPO / "examples" / "pf-core-valid"
INVALID = REPO / "examples" / "pf-core-invalid"
HASH_VECTORS = Path(__file__).resolve().parent / "hash_vectors" / "pf_core"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_runtime_observation_schema_requires_sequence() -> None:
    observation = _load(VALID / "file_read_allowed" / "observation.json")
    assert observation["sequence"] == 0
    event = compile_runtime_observation_to_event(observation)
    assert event["sequence"] == 0


def test_ordered_observation_compilation_uses_sequence() -> None:
    allow = _load(VALID / "file_read_allowed" / "observation.json")
    deny = _load(VALID / "network_denied" / "observation.json")
    allow = dict(allow)
    deny = dict(deny)
    allow["trace_id"] = "trace-order-1"
    allow["event_id"] = "ev-second"
    allow["sequence"] = 1
    deny["trace_id"] = "trace-order-1"
    deny["event_id"] = "ev-first"
    deny["sequence"] = 0

    trace = compile_runtime_observations_to_pfcore_trace([allow, deny])
    assert [event["event_id"] for event in trace["events"]] == ["ev-first", "ev-second"]
    assert [event["sequence"] for event in trace["events"]] == [0, 1]


def test_denied_observation_preserved_in_batch_compile() -> None:
    allow = _load(VALID / "file_read_allowed" / "observation.json")
    deny = _load(VALID / "network_denied" / "observation.json")
    for obs in (allow, deny):
        obs["trace_id"] = "trace-deny-batch"
    deny["sequence"] = 1
    allow["sequence"] = 0
    trace = compile_runtime_observations_to_pfcore_trace([allow, deny])
    validate_denied_observations_preserved([allow, deny], trace["events"])


def test_dropped_denied_observation_fixture() -> None:
    case = INVALID / "dropped_denied_observation"
    manifest = load_pf_core_fixture_manifest(case)
    observations = [_load(path) for path in sorted(case.glob("observation*.json"))]
    pfcore = _load(case / "pfcore_trace.json")
    with pytest.raises(DroppedDeniedEvent) as exc:
        validate_denied_observations_preserved(observations, pfcore["events"])
    assert exc.value.code == manifest["expected_error"]


def test_lean_kernel_checked_on_trace_rejected() -> None:
    trace = _load(INVALID / "lean_kernel_checked_on_trace" / "trace.json")
    errors = validate_semantics(trace, "PFCoreTrace.v0")
    assert any("ClaimClassOverclaim" in err for err in errors)


def test_default_trace_safe_contract_binding() -> None:
    trace = _load(VALID / "contract_checked" / "trace.json")
    assert trace_has_contract_binding(trace) is True
    trace = dict(trace)
    trace["default_contract_ref"] = DEFAULT_TRACE_SAFE_CONTRACT_ID
    trace["events"] = [
        dict(event, contract_refs=[]) for event in trace["events"] if isinstance(event, dict)
    ]
    assert trace_has_contract_binding(trace) is True


@pytest.mark.parametrize(
    "case_name",
    [
        "previous_event_hash_mismatch",
        "lean_kernel_checked_on_trace",
        "lean_kernel_checked_without_proof_ref",
        "lean_kernel_checked_without_proof_term_ref",
        "lean_kernel_checked_without_proof_term_hash",
        "lean_kernel_checked_with_skipped_build",
        "unknown_direct_trace_effect",
        "unknown_direct_trace_capability",
        "capability_effect_mismatch",
        "contract_ref_missing",
        "contract_capability_missing",
        "contract_effect_missing",
        "contract_policy_ref_missing",
        "contract_evidence_ref_missing",
        "dropped_denied_observation",
    ],
)
def test_invalid_fixture_manifest(case_name: str) -> None:
    manifest = load_pf_core_fixture_manifest(INVALID / case_name)
    assert manifest["expected_error"]
    assert manifest["must_fail_at"]


def test_invalid_fixture_harness_runs() -> None:
    check_pf_core_invalid_fixtures()


@pytest.mark.parametrize(
    "artifact",
    ["PFCoreEvent.v0", "PFCoreTrace.v0", "PFCoreContract.v0"],
)
def test_pf_core_hash_vectors(artifact: str) -> None:
    vector_dir = HASH_VECTORS / artifact
    payload = _load(vector_dir / "input.json")
    digest = (vector_dir / "digest.txt").read_text(encoding="utf-8").strip()
    canonical = (vector_dir / "canonical.txt").read_text(encoding="utf-8").strip()
    if artifact == "PFCoreEvent.v0":
        assert compute_event_hash(payload) == digest
    elif artifact == "PFCoreTrace.v0":
        assert compute_trace_hash(payload) == digest
    else:
        assert canonical_hash(payload) == digest
    stripped = canonicalize_for_hash(
        {k: v for k, v in payload.items() if k not in ("event_hash", "trace_hash", "signature_or_digest")}
    )
    assert json.dumps(stripped, separators=(",", ":"), ensure_ascii=False) == canonical.rstrip("\n")
