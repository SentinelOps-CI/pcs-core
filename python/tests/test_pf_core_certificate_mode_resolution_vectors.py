"""Normative hash vectors for resolve_certificate_mode release-grade policy parity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.hash import canonical_hash, canonical_json_bytes
from pcs_core.pf_core_lean_codegen import resolve_certificate_mode

VECTOR_FILE = (
    Path(__file__).resolve().parent
    / "hash_vectors"
    / "pf_core"
    / "certificate_mode_resolution"
    / "vectors.json"
)


def _load_vectors() -> list[dict]:
    payload = json.loads(VECTOR_FILE.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("certificate_mode_resolution vectors must contain a cases list")
    return cases


def _case_payload(case: dict) -> dict:
    return {
        "case_id": case["case_id"],
        "release_grade": case["release_grade"],
        "has_sibling_tool_use_trace": case["has_sibling_tool_use_trace"],
        "trace": case["trace"],
        "expected_mode": case["expected_mode"],
    }


@pytest.mark.parametrize("case", _load_vectors(), ids=lambda case: case["case_id"])
def test_certificate_mode_resolution_vector(case: dict, tmp_path: Path) -> None:
    payload = _case_payload(case)
    assert canonical_hash(payload) == case["expected_digest"]
    assert canonical_json_bytes(payload).decode("utf-8") == case["canonical_json"]

    trace_file = tmp_path / "pfcore_trace.json"
    trace_file.write_text(json.dumps(case["trace"]), encoding="utf-8")
    if case["has_sibling_tool_use_trace"]:
        (tmp_path / "tool_use_trace.json").write_text("{}", encoding="utf-8")

    mode = resolve_certificate_mode(
        case["trace"],
        trace_path=trace_file,
        release_grade=bool(case["release_grade"]),
    )
    assert mode == case["expected_mode"]
