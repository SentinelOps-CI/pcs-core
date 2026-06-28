"""Tests for PF-Core Phase H research items (state, cross-tenant NI, RoleMap parity)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from pcs_core.lean_catalog import PF_CORE_THEOREM_CATALOG
from pcs_core.pf_core_claims import audit_lean_catalog
from pcs_core.pf_core_runtime import ROLE_CAPABILITY_MAP

REPO = Path(__file__).resolve().parents[2]

RESEARCH_THEOREMS = frozenset(
    {
        "handoff_preserves_trace_safe",
        "traceSafe_implies_trace_cross_tenant_safe",
        "runtime_role_expansion_subset",
    }
)

RESEARCH_HELPER_THEOREMS = frozenset(
    {
        "handoff_applies_does_not_expand_authority",
        "traceSafe_implies_cross_tenant_safe",
    }
)

ROLE_MAP_KEYS_PATTERN = re.compile(
    r"def runtimeRoleMap\s*:\s*RoleMap\s*:=\s*\{\s*entries\s*:=\s*\[(.*?)\]\s*\}",
    re.DOTALL,
)
ROLE_ENTRY_PATTERN = re.compile(r'\(\s*"([^"]+)"\s*,')


def _lean_source(name: str) -> str:
    path = REPO / "lean" / "PFCore" / name
    assert path.is_file(), f"missing Lean module: {path}"
    return path.read_text(encoding="utf-8")


def _extract_runtime_role_map_keys() -> set[str]:
    text = _lean_source("RoleMap.lean")
    match = ROLE_MAP_KEYS_PATTERN.search(text)
    assert match, "runtimeRoleMap entries block not found in RoleMap.lean"
    return set(ROLE_ENTRY_PATTERN.findall(match.group(1)))


def test_research_theorems_in_catalog() -> None:
    missing = RESEARCH_THEOREMS - PF_CORE_THEOREM_CATALOG
    assert not missing, f"missing from PF_CORE_THEOREM_CATALOG: {sorted(missing)}"


def test_research_lean_catalog_audit() -> None:
    errors = audit_lean_catalog()
    research_errors = [err for err in errors if any(name in err for name in RESEARCH_THEOREMS)]
    assert research_errors == [], research_errors


def test_research_lean_modules_exist_without_sorry() -> None:
    for module in ("State.lean", "NonInterference.lean", "RoleMap.lean"):
        text = _lean_source(module)
        assert "sorry" not in text, f"sorry found in {module}"
        assert "admit" not in text, f"admit found in {module}"
    for theorem in RESEARCH_HELPER_THEOREMS:
        assert any(
            theorem in path.read_text(encoding="utf-8")
            for path in (REPO / "lean" / "PFCore").glob("*.lean")
        ), f"helper theorem missing: {theorem}"


def test_runtime_role_map_keys_match_python() -> None:
    lean_keys = _extract_runtime_role_map_keys()
    python_keys = set(ROLE_CAPABILITY_MAP.keys())
    assert lean_keys == python_keys, (
        f"RoleMap key mismatch: lean-only={sorted(lean_keys - python_keys)}, "
        f"python-only={sorted(python_keys - lean_keys)}"
    )


def test_runtime_role_map_capability_values_match_python() -> None:
    """Audit capability lists per role via static parse of runtimeRoleMap entries."""
    text = _lean_source("RoleMap.lean")
    match = ROLE_MAP_KEYS_PATTERN.search(text)
    assert match
    entries_blob = match.group(1)
    lean_map: dict[str, list[str]] = {}
    for role_match in re.finditer(r'\(\s*"([^"]+)"\s*,\s*\[(.*?)\]\s*\)', entries_blob, re.DOTALL):
        role = role_match.group(1)
        caps_blob = role_match.group(2)
        caps = re.findall(r'"([^"]+)"', caps_blob)
        lean_map[role] = caps
    assert lean_map == ROLE_CAPABILITY_MAP


def test_state_module_theorems_present() -> None:
    text = _lean_source("State.lean")
    assert "theorem handoff_preserves_trace_safe" in text
    assert "theorem handoff_applies_does_not_expand_authority" in text
    assert "def HandoffApplies" in text
    assert "def applyEvent" in text


def test_non_interference_cross_tenant_theorems_present() -> None:
    text = _lean_source("NonInterference.lean")
    assert "def CrossTenantDenied" in text
    assert "def TraceCrossTenantSafe" in text
    assert "theorem traceSafe_implies_trace_cross_tenant_safe" in text


@pytest.mark.parametrize(
    "theorem",
    sorted(RESEARCH_THEOREMS & PF_CORE_THEOREM_CATALOG),
)
def test_cataloged_research_theorem_in_lean_sources(theorem: str) -> None:
    pfcore_dir = REPO / "lean" / "PFCore"
    found = any(theorem in path.read_text(encoding="utf-8") for path in pfcore_dir.glob("*.lean"))
    assert found, f"{theorem!r} not found in lean/PFCore/*.lean"


def test_python_role_capability_map_is_static_dict() -> None:
    """ROLE_CAPABILITY_MAP must remain a module-level dict for parity audits."""
    runtime_path = REPO / "python" / "pcs_core" / "pf_core_runtime.py"
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"))
    found = False
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "ROLE_CAPABILITY_MAP" and isinstance(node.value, ast.Dict):
                found = True
                break
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "ROLE_CAPABILITY_MAP" for t in node.targets):
                found = True
                break
    assert found
