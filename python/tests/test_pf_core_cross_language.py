"""Cross-language PF-Core schema registration and artifact_type detection parity."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from pcs_core.pf_core_runtime import compute_event_hash, compute_trace_hash, validate_pfcore_trace_hash_chain
from pcs_core.validate import ARTIFACT_SCHEMAS, detect_artifact_type, validate_schema

REPO = Path(__file__).resolve().parents[2]

PF_CORE_TYPES = sorted(
    key
    for key in ARTIFACT_SCHEMAS
    if key.startswith("PFCore") or key in {"ToolUseTrace.v0", "LeanCheckResult.v0", "PCSBridgeCertificate.v0"}
)

TS_SCHEMAS = REPO / "typescript" / "packages" / "core" / "src" / "schema.ts"
RUST_SCHEMAS = REPO / "rust" / "crates" / "pcs-core" / "src" / "validation.rs"
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "pfcore_trace.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_quoted_types(path: Path, marker: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    block = text.split(marker, 1)[-1]
    return set(re.findall(r'"((?:PFCore|ToolUseTrace|LeanCheckResult|PCSBridgeCertificate)[^"]+)"', block))


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
    result = subprocess.run(
        ["npm", "test"],
        cwd=REPO / "typescript",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
