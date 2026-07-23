"""Phase 4: catalog completeness, semantic projection, theorem status fields."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pcs_core.hash import canonical_hash
from pcs_core.lean_catalog import PF_CORE_THEOREM_CATALOG
from pcs_core.lean_check import (
    normalize_theorem_status_fields,
    pfcore_theorem_status,
    pfcore_theorems_checked,
)
from pcs_core.pf_core_catalog import EFFECT_KIND_TO_LEAN, ROLE_CAPABILITY_MAP
from pcs_core.pf_core_lean_codegen import (
    effect_kind_to_lean,
    generate_proof_obligation_file,
    resolve_certificate_mode,
)
from pcs_core.pf_core_semantic_projection import (
    build_semantic_projection,
    projection_to_codegen_trace,
)
from pcs_core.validate import validate_artifact

REPO = Path(__file__).resolve().parents[2]
CATALOG_LEAN = REPO / "lean" / "PFCore" / "Catalog.lean"
VALID_TRACE = REPO / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json"


def test_catalog_lean_emits_full_derivatives() -> None:
    text = CATALOG_LEAN.read_text(encoding="utf-8")
    for symbol in (
        "knownCapabilityEffectCatalog",
        "effectKindToEffect",
        "knownCustomEffectLabels",
        "runtimeRoleMapEntries",
        "toolMapEntries",
        "workflowCertificateModeEntries",
        "capabilityPatternString",
    ):
        assert f"def {symbol}" in text, f"missing generated symbol {symbol}"


def test_effect_kind_to_lean_comes_from_generated_catalog() -> None:
    codegen = (REPO / "python" / "pcs_core" / "pf_core_lean_codegen.py").read_text(encoding="utf-8")
    assert "EFFECT_KIND_TO_LEAN: dict[str, str] = {" not in codegen
    assert "from pcs_core.pf_core_catalog import EFFECT_KIND_TO_LEAN" in codegen
    assert effect_kind_to_lean("file.write") == EFFECT_KIND_TO_LEAN["file.write"]
    assert effect_kind_to_lean("lab.release") == EFFECT_KIND_TO_LEAN["lab.release"]


def test_action_lean_does_not_hand_maintain_effect_catalog() -> None:
    action = (REPO / "lean" / "PFCore" / "Action.lean").read_text(encoding="utf-8")
    assert "Catalog.knownCapabilityEffectCatalog" in action
    assert '("cap:file-read", Effect.read)' not in action


def test_semantic_projection_hash_stable_and_independent(tmp_path: Path) -> None:
    trace = json.loads(VALID_TRACE.read_text(encoding="utf-8"))
    mode = resolve_certificate_mode(trace, trace_path=VALID_TRACE)
    projection = build_semantic_projection(trace, certificate_mode=mode, trace_path=VALID_TRACE)
    assert projection["artifact_type"] == "PFCoreSemanticProjection.v0"
    assert projection["projection_hash"].startswith("sha256:")
    body = {k: v for k, v in projection.items() if k != "projection_hash"}
    assert canonical_hash(body) == projection["projection_hash"]
    validate_artifact(projection, "PFCoreSemanticProjection.v0")

    # Envelope noise must not change projection hash.
    noisy = dict(trace)
    noisy["source_commit"] = "deadbeefdeadbeef"
    noisy["extra_non_lean_field"] = {"foo": 1}
    projection2 = build_semantic_projection(noisy, certificate_mode=mode, trace_path=VALID_TRACE)
    assert projection2["projection_hash"] == projection["projection_hash"]


def test_codegen_binds_semantic_projection_hash(tmp_path: Path) -> None:
    trace = json.loads(VALID_TRACE.read_text(encoding="utf-8"))
    generated = generate_proof_obligation_file(trace, tmp_path, trace_path=VALID_TRACE)
    assert generated.semantic_projection_hash
    assert generated.semantic_projection_hash.startswith("sha256:")
    source = generated.path.read_text(encoding="utf-8")
    assert generated.semantic_projection_hash in source
    assert "concrete_trace_safe" in generated.theorem_names


def test_theorem_status_distinguishes_availability_from_execution() -> None:
    status = pfcore_theorem_status(
        lean_kernel=True,
        concrete_generated=["concrete_trace_safe", "concrete_trace_safe_prop"],
        concrete_compiled=["concrete_trace_safe"],
    )
    assert status["kernel_theorems_available"] == sorted(PF_CORE_THEOREM_CATALOG)
    assert status["concrete_theorems_generated"] == [
        "concrete_trace_safe",
        "concrete_trace_safe_prop",
    ]
    assert status["concrete_theorems_compiled"] == ["concrete_trace_safe"]
    # Legacy compat remains a fixed catalog union.
    assert pfcore_theorems_checked(lean_kernel=True) != status["concrete_theorems_generated"]


def test_normalize_theorem_status_from_legacy_theorems_checked() -> None:
    legacy = {
        "lean_proof_checked": True,
        "theorems_checked": sorted(PF_CORE_THEOREM_CATALOG | {"concrete_trace_safe"}),
    }
    normalized = normalize_theorem_status_fields(legacy)
    assert "concrete_trace_safe" in normalized["concrete_theorems_generated"]
    assert set(normalized["kernel_theorems_available"]) <= PF_CORE_THEOREM_CATALOG


def test_projection_roundtrip_preserves_lean_fields() -> None:
    trace = json.loads(VALID_TRACE.read_text(encoding="utf-8"))
    mode = resolve_certificate_mode(trace, trace_path=VALID_TRACE)
    projection = build_semantic_projection(trace, certificate_mode=mode, trace_path=VALID_TRACE)
    rehydrated = projection_to_codegen_trace(projection)
    assert len(rehydrated["events"]) == len(trace["events"])
    original_action = trace["events"][0]["action"]
    projected_action = rehydrated["events"][0]["action"]
    assert (
        projected_action["capability"]["capability_id"]
        == original_action["capability"]["capability_id"]
    )
    assert (
        projected_action["capability"]["effect_kind"]
        == original_action["capability"]["effect_kind"]
    )


def test_role_map_entries_match_python_catalog() -> None:
    text = CATALOG_LEAN.read_text(encoding="utf-8")
    match = re.search(
        r"def runtimeRoleMapEntries\s*:\s*List\s*\(String\s*×\s*List\s*String\)\s*:=\s*"
        r"\[\s*(.*?)\s*\]\s*\n\n/-- Tool name",
        text,
        re.DOTALL,
    )
    assert match
    lean_map: dict[str, list[str]] = {}
    for role_match in re.finditer(
        r'\(\s*"([^"]+)"\s*,\s*\[(.*?)\]\s*\)', match.group(1), re.DOTALL
    ):
        lean_map[role_match.group(1)] = re.findall(r'"([^"]+)"', role_match.group(2))
    assert lean_map == ROLE_CAPABILITY_MAP
