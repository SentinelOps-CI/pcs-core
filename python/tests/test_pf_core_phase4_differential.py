"""Cross-language PF-Core decider differential tests (Phase 4.2).

Compares Python semantic validation outcomes on shared effect/capability fixtures.
Rust/TypeScript parity remains covered by ``test_pf_core_cross_language.py``.
Lean JSON decoding is deferred (codegen + lake remain the bridge); generated Lean
theorem inventories are checked where codegen is available.
"""

from __future__ import annotations

import json
from pathlib import Path

from pcs_core.pf_core_catalog import CAPABILITY_CATALOG, EFFECT_KINDS
from pcs_core.pf_core_lean_codegen import generate_proof_obligation_file, resolve_certificate_mode
from pcs_core.validate import validate_semantics

REPO = Path(__file__).resolve().parents[2]
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json"
INVALID_EXAMPLES = REPO / "examples" / "pf-core-invalid"
HASH_VECTORS = REPO / "python" / "tests" / "hash_vectors" / "pf_core"

LEAN_JSON_DECODER_STATUS = (
    "deferred: no restricted PF-Core Lean JSON decoder in v0; "
    "semantic projection + Python codegen is the trusted bridge"
)

DIFFERENTIAL_CASES: tuple[tuple[Path, str], ...] = (
    (INVALID_EXAMPLES / "unknown_direct_trace_effect" / "trace.json", "UnknownEffect"),
    (INVALID_EXAMPLES / "capability_effect_mismatch" / "trace.json", "CapabilityEffectMismatch"),
    (INVALID_EXAMPLES / "unknown_direct_trace_capability" / "trace.json", "UnknownCapability"),
    (HASH_VECTORS / "invalid" / "unknown_direct_trace_effect.json", "UnknownEffect"),
    (HASH_VECTORS / "invalid" / "capability_effect_mismatch.json", "CapabilityEffectMismatch"),
    (HASH_VECTORS / "invalid" / "unknown_direct_trace_capability.json", "UnknownCapability"),
)


def test_python_decider_rejects_catalog_mismatches() -> None:
    for path, needle in DIFFERENTIAL_CASES:
        assert path.is_file(), path
        errors = validate_semantics(json.loads(path.read_text(encoding="utf-8")), "PFCoreTrace.v0")
        assert any(needle in err for err in errors), (path, errors)


def test_catalog_effect_kinds_cover_capability_effects() -> None:
    for cap_id, entry in CAPABILITY_CATALOG.items():
        assert entry["effect_kind"] in EFFECT_KINDS, cap_id


def test_generated_lean_theorem_result_for_valid_trace(tmp_path: Path) -> None:
    """Generated Lean theorem inventory is available when codegen succeeds."""
    trace = json.loads(VALID_TRACE.read_text(encoding="utf-8"))
    assert validate_semantics(trace, "PFCoreTrace.v0") == []
    generated = generate_proof_obligation_file(trace, tmp_path, trace_path=VALID_TRACE)
    assert "concrete_trace_safe" in generated.theorem_names
    assert generated.certificate_mode == resolve_certificate_mode(trace, trace_path=VALID_TRACE)
    assert generated.semantic_projection_hash
    assert generated.semantic_projection_hash.startswith("sha256:")


def test_a11_base_vs_refined_resource_pattern_differential() -> None:
    """A11: out-of-pattern URI → TraceSafe true, TraceSafeR false."""
    from pcs_core.lean_check import trace_safe_d, trace_safe_rd

    path = INVALID_EXAMPLES / "resource_scope_violation" / "trace.json"
    events = json.loads(path.read_text(encoding="utf-8"))["events"]
    assert trace_safe_d(events) is True
    assert trace_safe_rd(events) is False


def test_lean_json_decoder_deferred_documented() -> None:
    assert "deferred" in LEAN_JSON_DECODER_STATUS
    docs = (REPO / "docs" / "pf-core" / "semantic-projection.md").read_text(encoding="utf-8")
    assert "Lean JSON decoder" in docs
    assert "deferred" in docs.lower()
