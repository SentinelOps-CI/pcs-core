"""Cross-language PF-Core schema registration and artifact_type detection parity."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from pcs_core.pf_core_contract import validate_trace_contracts
from pcs_core.pf_core_runtime import (
    compute_event_hash,
    compute_trace_hash,
    validate_denied_events_preserved,
    validate_pfcore_trace_hash_chain,
)
from pcs_core.validate import ARTIFACT_SCHEMAS, detect_artifact_type

REPO = Path(__file__).resolve().parents[2]
INVALID_VECTORS = REPO / "python" / "tests" / "hash_vectors" / "pf_core" / "invalid"

PF_CORE_TYPES = sorted(
    key
    for key in ARTIFACT_SCHEMAS
    if key.startswith("PFCore")
    or key in {"ToolUseTrace.v0", "LeanCheckResult.v0", "PCSBridgeCertificate.v0"}
)

TS_SCHEMAS = REPO / "typescript" / "packages" / "core" / "src" / "schema.ts"
RUST_SCHEMAS = REPO / "rust" / "crates" / "pcs-core" / "src" / "validation.rs"
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_quoted_types(path: Path, marker: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    block = text.split(marker, 1)[-1]
    return set(
        re.findall(r'"((?:PFCore|ToolUseTrace|LeanCheckResult|PCSBridgeCertificate)[^"]+)"', block)
    )


def test_python_pf_core_schemas_registered() -> None:
    for artifact_type in PF_CORE_TYPES:
        assert artifact_type in ARTIFACT_SCHEMAS


def test_typescript_registers_same_pf_core_schemas() -> None:
    ts_types = _extract_quoted_types(TS_SCHEMAS, "const ARTIFACT_SCHEMAS")
    assert set(PF_CORE_TYPES).issubset(ts_types)


def test_rust_registers_same_pf_core_schemas() -> None:
    rust_types = _extract_quoted_types(RUST_SCHEMAS, "const ARTIFACT_SCHEMAS")
    assert set(PF_CORE_TYPES).issubset(rust_types)


@pytest.mark.parametrize(
    "relative",
    [
        "examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json",
        "examples/pf-core-valid/contract_checked/trace.json",
        "examples/pf-core-valid/handoff_subset_authority/handoff.json",
        "examples/pf-core-valid/assumption_declared/certificate.json",
    ],
)
def test_python_explicit_artifact_type_detection(relative: str) -> None:
    path = REPO / relative
    data = _load_json(path)
    detected = detect_artifact_type(data)
    assert detected == data["artifact_type"]


def test_pf_core_trace_not_detected_as_trace_certificate() -> None:
    trace = _load_json(REPO / "examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json")
    assert detect_artifact_type(trace) == "PFCoreTrace.v0"
    assert detect_artifact_type(trace) != "TraceCertificate.v0"


@pytest.mark.parametrize("artifact_type", PF_CORE_TYPES)
def test_pf_core_schema_files_exist(artifact_type: str) -> None:
    schema_path = REPO / "schemas" / ARTIFACT_SCHEMAS[artifact_type]
    assert schema_path.is_file(), f"missing schema for {artifact_type}"


def test_python_pf_core_trace_hash_chain_valid_fixture() -> None:
    trace = _load_json(VALID_TRACE)
    assert validate_pfcore_trace_hash_chain(trace) == []


def test_python_pf_core_trace_hash_recompute() -> None:
    trace = _load_json(VALID_TRACE)
    assert compute_trace_hash(trace) == trace["trace_hash"]
    for event in trace["events"]:
        assert compute_event_hash(event) == event["event_hash"]


def test_python_claim_class_overclaim_on_trace() -> None:
    trace = _load_json(VALID_TRACE)
    trace = dict(trace)
    trace["claim_class"] = "LeanKernelChecked"
    errors = validate_pfcore_trace_hash_chain(trace)
    assert any("ClaimClassOverclaim" in err for err in errors)


def test_python_pf_core_shared_hash_vectors() -> None:
    vector_root = REPO / "python" / "tests" / "hash_vectors" / "pf_core"
    for name in ("PFCoreEvent.v0", "PFCoreTrace.v0", "PFCoreContract.v0"):
        payload = _load_json(vector_root / name / "input.json")
        digest = (vector_root / name / "digest.txt").read_text(encoding="utf-8").strip()
        if name == "PFCoreEvent.v0":
            assert compute_event_hash(payload) == digest
        elif name == "PFCoreTrace.v0":
            assert compute_trace_hash(payload) == digest
        else:
            from pcs_core.hash import canonical_hash

            assert canonical_hash(payload) == digest


@pytest.mark.parametrize(
    "relative,needle",
    [
        ("invalid/trace_hash_chain_break.json", "EventHashMismatch"),
        ("invalid/claim_class_overclaim_trace.json", "ClaimClassOverclaim"),
        ("invalid/trace_hash_mismatch.json", "TraceHashMismatch"),
        ("invalid/previous_event_hash_mismatch.json", "EventHashMismatch"),
    ],
)
def test_python_invalid_pf_core_vectors(relative: str, needle: str) -> None:
    trace = _load_json(REPO / "python" / "tests" / "hash_vectors" / "pf_core" / relative)
    errors = validate_pfcore_trace_hash_chain(trace)
    assert any(needle in err for err in errors)


def test_python_denied_event_preserved_invalid_vector() -> None:
    from pcs_core.pf_core_runtime import DroppedDeniedEvent, validate_denied_events_preserved

    root = (
        REPO / "python" / "tests" / "hash_vectors" / "pf_core" / "invalid" / "denied_event_dropped"
    )
    tool_use = _load_json(root / "tool_use_trace.json")
    pfcore = _load_json(root / "pfcore_trace.json")
    with pytest.raises(DroppedDeniedEvent):
        validate_denied_events_preserved(tool_use, pfcore)


def test_rust_pf_core_detection_tests_pass() -> None:
    result = subprocess.run(
        ["cargo", "test", "pf_core", "--", "--nocapture"],
        cwd=REPO / "rust",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_typescript_pf_core_detection_tests_pass() -> None:
    if sys.platform == "win32":
        pytest.skip("typescript workspace test runner uses shell globs unavailable on Windows")
    ts_root = REPO / "typescript"
    install = subprocess.run(
        ["npm", "install", "--silent"],
        cwd=ts_root,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    result = subprocess.run(
        ["npm", "test"],
        cwd=ts_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_shared_negative_vectors_python() -> None:
    trace = _load_json(INVALID_VECTORS / "trace_hash_chain_break.json")
    assert any("EventHashMismatch" in err for err in validate_pfcore_trace_hash_chain(trace))

    overclaim = _load_json(INVALID_VECTORS / "claim_class_overclaim_trace.json")
    assert any("ClaimClassOverclaim" in err for err in validate_pfcore_trace_hash_chain(overclaim))

    trace_mismatch = _load_json(INVALID_VECTORS / "trace_hash_mismatch.json")
    assert any(
        "TraceHashMismatch" in err for err in validate_pfcore_trace_hash_chain(trace_mismatch)
    )

    prev_mismatch = _load_json(INVALID_VECTORS / "previous_event_hash_mismatch.json")
    assert any(
        "EventHashMismatch" in err for err in validate_pfcore_trace_hash_chain(prev_mismatch)
    )

    from pcs_core.pf_core_runtime import validate_tenant_isolation

    cross_tenant = _load_json(INVALID_VECTORS / "cross_tenant_leak.json")
    assert any("TenantIsolation" in err for err in validate_tenant_isolation(cross_tenant))

    contract_dir = INVALID_VECTORS / "contract_capability_missing"
    contract_trace = _load_json(contract_dir / "trace.json")
    contract = _load_json(contract_dir / "contract.json")
    issues = validate_trace_contracts(contract_trace, {contract["contract_id"]: contract})
    assert any(issue.code == "ContractCapabilityRequired" for issue in issues)

    denied_dir = INVALID_VECTORS / "denied_event_dropped"
    with pytest.raises(Exception):
        validate_denied_events_preserved(
            _load_json(denied_dir / "tool_use_trace.json"),
            _load_json(denied_dir / "pfcore_trace.json"),
        )


def test_rust_negative_vector_tests_in_pf_core_suite() -> None:
    result = subprocess.run(
        ["cargo", "test", "pf_core_", "--", "--nocapture"],
        cwd=REPO / "rust",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
