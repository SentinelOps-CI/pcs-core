"""Tests for generated PF-Core catalog tool_map and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.pf_core_catalog import CAPABILITY_CATALOG, EFFECT_KINDS, TOOL_NAME_MAP
from pcs_core.pf_core_runtime import compile_tool_use_trace_to_pfcore_trace

REPO = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO / "catalog" / "pf_core.catalog.json"
TOOL_USE = REPO / "examples" / "pf-core-valid" / "tool_use_trace_compiled" / "tool_use_trace.json"


def test_tool_name_map_matches_catalog() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    tool_map = catalog["tool_map"]
    assert len(TOOL_NAME_MAP) == len(tool_map)
    for entry in tool_map:
        key = (entry["tool_name"], entry["tool_category"])
        assert key in TOOL_NAME_MAP
        cap_id, effect_kind, pattern = TOOL_NAME_MAP[key]
        assert cap_id == entry["capability_id"]
        assert effect_kind
        assert pattern


def test_generated_effect_kind_to_lean_covers_catalog() -> None:
    from pcs_core.pf_core_catalog import EFFECT_KIND_TO_LEAN

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    for kind in catalog["effect_kinds"]:
        assert kind in EFFECT_KIND_TO_LEAN
        assert EFFECT_KIND_TO_LEAN[kind].startswith("Effect.")
    assert set(CAPABILITY_CATALOG[c]["effect_kind"] for c in CAPABILITY_CATALOG) <= EFFECT_KINDS


def test_compile_tool_use_trace_uses_catalog_tool_map() -> None:
    tool_use = json.loads(TOOL_USE.read_text(encoding="utf-8"))
    compiled = compile_tool_use_trace_to_pfcore_trace(tool_use)
    assert compiled["events"]


def test_catalog_generator_rejects_unsupported_resource_patterns(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gen_pf_core_catalog",
        REPO / "python" / "scripts" / "gen_pf_core_catalog.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validate_catalog = module.validate_catalog

    bad = {
        "capabilities": [
            {
                "capability_id": "cap:bad",
                "effect_kind": "file.read",
                "resource_pattern": "/data/**",
            }
        ],
        "role_map": {},
        "effect_kinds": ["file.read"],
        "tool_map": [
            {
                "tool_name": "filesystem.read",
                "tool_category": "filesystem",
                "capability_id": "cap:bad",
            }
        ],
    }
    with pytest.raises(ValueError, match="unsupported resource_pattern"):
        validate_catalog(bad)
