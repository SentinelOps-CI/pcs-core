"""Generate PF-Core catalog artifacts from catalog/pf_core.catalog.json."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from pcs_core.paths import repo_root

CATALOG_PATH = repo_root() / "catalog" / "pf_core.catalog.json"

_UNSUPPORTED_RESOURCE_PATTERN_RE = re.compile(r"[\?\[\]\{\}]|\*\*")


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def validate_catalog(catalog: dict) -> None:
    """Reject catalog entries whose resource patterns exceed the Lean glob subset."""
    caps = catalog.get("capabilities")
    if not isinstance(caps, list):
        raise ValueError("catalog.capabilities must be a list")
    cap_ids = {str(cap["capability_id"]) for cap in caps if isinstance(cap, dict)}
    for cap in caps:
        if not isinstance(cap, dict):
            raise ValueError("catalog.capabilities entries must be objects")
        pattern = str(cap.get("resource_pattern") or "")
        if _UNSUPPORTED_RESOURCE_PATTERN_RE.search(pattern):
            raise ValueError(
                f"unsupported resource_pattern for Lean glob subset: {pattern!r} "
                f"(capability {cap.get('capability_id')!r})"
            )
    tool_map = catalog.get("tool_map")
    if not isinstance(tool_map, list):
        raise ValueError("catalog.tool_map must be a list")
    seen: set[tuple[str, str]] = set()
    for entry in tool_map:
        if not isinstance(entry, dict):
            raise ValueError("catalog.tool_map entries must be objects")
        tool_name = str(entry.get("tool_name") or "")
        tool_category = str(entry.get("tool_category") or "")
        cap_id = str(entry.get("capability_id") or "")
        if not tool_name or not tool_category or not cap_id:
            raise ValueError(f"invalid tool_map entry: {entry!r}")
        if cap_id not in cap_ids:
            raise ValueError(f"tool_map references unknown capability_id {cap_id!r}")
        key = (tool_name, tool_category)
        if key in seen:
            raise ValueError(f"duplicate tool_map key {key!r}")
        seen.add(key)


def _py_repr(value: object) -> str:
    return repr(value)


def generate_python(catalog: dict, out_path: Path) -> str:
    caps = catalog["capabilities"]
    role_map = catalog["role_map"]
    effect_kinds = catalog["effect_kinds"]
    cap_lines = []
    for cap in caps:
        cap_id = _py_repr(cap["capability_id"])
        cap_lines.append(
            f"    {cap_id}: {{\n"
            f'        "capability_id": {_py_repr(cap["capability_id"])},\n'
            f'        "effect_kind": {_py_repr(cap["effect_kind"])},\n'
            f'        "resource_pattern": {_py_repr(cap["resource_pattern"])},\n'
            f"    }},"
        )
    role_lines = []
    for role, caps_list in role_map.items():
        role_lines.append(f"    {_py_repr(role)}: {_py_repr(caps_list)},")
    tool_map = catalog["tool_map"]
    tool_lines = []
    for entry in tool_map:
        cap_id = entry["capability_id"]
        tool_lines.append(
            f"    ({_py_repr(entry['tool_name'])}, {_py_repr(entry['tool_category'])}): "
            f"({_py_repr(cap_id)}, "
            f"{_py_repr(next(c['effect_kind'] for c in caps if c['capability_id'] == cap_id))}, "
            f"{_py_repr(next(c['resource_pattern'] for c in caps if c['capability_id'] == cap_id))}),"
        )
    effect_lines = ",\n    ".join(_py_repr(e) for e in effect_kinds)
    source = f'''"""Generated PF-Core catalog (do not edit by hand)."""

from __future__ import annotations

EFFECT_KINDS = frozenset([
    {effect_lines},
])

CAPABILITY_CATALOG: dict[str, dict[str, str]] = {{
{chr(10).join(cap_lines)}
}}

ROLE_CAPABILITY_MAP: dict[str, list[str]] = {{
{chr(10).join(role_lines)}
}}

TOOL_NAME_MAP: dict[tuple[str, str], tuple[str, str, str]] = {{
{chr(10).join(tool_lines)}
}}
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    return source


def generate_lean(catalog: dict, out_path: Path) -> str:
    caps = catalog["capabilities"]
    cap_ids = [cap["capability_id"] for cap in caps]
    cap_id_lines = "\n".join(f'  , "{cap}"' for cap in cap_ids[1:])
    patterns = [cap["resource_pattern"] for cap in caps]
    pattern_lines = "\n".join(f'  , ResourcePattern.glob "{pat}"' for pat in patterns[1:])
    pattern_cases = "\n".join(
        f'  | "{cap["capability_id"]}" => "{cap["resource_pattern"]}"' for cap in caps
    )
    source = f'''/-!
# PF-Core generated capability catalog (do not edit by hand).
-/

namespace PFCore.Catalog

def knownCatalogCaps : List String :=
  [ "{cap_ids[0]}"
{cap_id_lines}
  ]

def catalogResourcePatternStrings : List String :=
  [ "{patterns[0]}"
{chr(10).join(f'  , "{pat}"' for pat in patterns[1:])}
  ]

def capabilityPatternString (cap : String) : String :=
  match cap with
{pattern_cases}
  | _ => ""

end PFCore.Catalog
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    return source


def generate_rust(catalog: dict, out_path: Path) -> str:
    caps = catalog["capabilities"]
    role_map = catalog["role_map"]
    effect_kinds = catalog["effect_kinds"]
    tool_map = catalog["tool_map"]
    cap_by_id = {cap["capability_id"]: cap for cap in caps}
    cap_entries = []
    for cap in caps:
        cap_entries.append(
            f'        ("{cap["capability_id"]}", "{cap["effect_kind"]}", "{cap["resource_pattern"]}"),'
        )
    role_entries = []
    for role, caps_list in role_map.items():
        items = ", ".join(f'"{c}"' for c in caps_list)
        role_entries.append(f'        ("{role}", &[{items}]),')
    tool_entries = []
    for entry in tool_map:
        cap = cap_by_id[entry["capability_id"]]
        tool_entries.append(
            "        ("
            f'"{entry["tool_name"]}", "{entry["tool_category"]}", '
            f'"{cap["capability_id"]}", "{cap["effect_kind"]}", "{cap["resource_pattern"]}"'
            "),"
        )
    effect_items = ", ".join(f'"{e}"' for e in effect_kinds)
    source = f"""//! Generated PF-Core catalog (do not edit by hand).

pub const EFFECT_KINDS: &[&str] = &[{effect_items}];

pub const CAPABILITY_CATALOG: &[(&str, &str, &str)] = &[
{chr(10).join(cap_entries)}
];

pub const ROLE_CAPABILITY_MAP: &[(&str, &[&str])] = &[
{chr(10).join(role_entries)}
];

pub const TOOL_NAME_MAP: &[(&str, &str, &str, &str, &str)] = &[
{chr(10).join(tool_entries)}
];
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    return source


def generate_typescript(catalog: dict, out_path: Path) -> str:
    caps = catalog["capabilities"]
    role_map = catalog["role_map"]
    effect_kinds = catalog["effect_kinds"]
    tool_map = catalog["tool_map"]
    cap_by_id = {cap["capability_id"]: cap for cap in caps}
    cap_lines = []
    for cap in caps:
        cap_lines.append(
            f"  {_py_repr(cap['capability_id'])}: {{ capability_id: {_py_repr(cap['capability_id'])}, "
            f"effect_kind: {_py_repr(cap['effect_kind'])}, "
            f"resource_pattern: {_py_repr(cap['resource_pattern'])} }},"
        )
    role_lines = []
    for role, caps_list in role_map.items():
        role_lines.append(f"  {_py_repr(role)}: {_py_repr(caps_list)},")
    tool_lines = []
    for entry in tool_map:
        cap = cap_by_id[entry["capability_id"]]
        key = f"{entry['tool_name']}|{entry['tool_category']}"
        tool_lines.append(
            f"  {_py_repr(key)}: "
            f"[{_py_repr(cap['capability_id'])}, {_py_repr(cap['effect_kind'])}, "
            f"{_py_repr(cap['resource_pattern'])}],"
        )
    effect_items = ", ".join(_py_repr(e) for e in effect_kinds)
    source = f"""/** Generated PF-Core catalog (do not edit by hand). */

export const EFFECT_KINDS = new Set<string>([{effect_items}]);

export const CAPABILITY_CATALOG: Record<
  string,
  {{ capability_id: string; effect_kind: string; resource_pattern: string }}
> = {{
{chr(10).join(cap_lines)}
}};

export const ROLE_CAPABILITY_MAP: Record<string, string[]> = {{
{chr(10).join(role_lines)}
}};

export const TOOL_NAME_MAP: Record<string, [string, string, string]> = {{
{chr(10).join(tool_lines)}
}};
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    return source


def main() -> None:
    catalog = load_catalog()
    validate_catalog(catalog)
    root = repo_root()
    py_catalog = root / "python" / "pcs_core" / "pf_core_catalog.py"
    generate_python(catalog, py_catalog)
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", str(py_catalog)],
        check=True,
    )
    generate_lean(catalog, root / "lean" / "PFCore" / "Catalog.lean")
    rust_catalog = root / "rust" / "crates" / "pcs-core" / "src" / "pf_core_catalog.rs"
    generate_rust(catalog, rust_catalog)
    subprocess.run(
        ["cargo", "fmt", "--", "crates/pcs-core/src/pf_core_catalog.rs"],
        cwd=root / "rust",
        check=True,
    )
    generate_typescript(
        catalog,
        root / "typescript" / "packages" / "core" / "src" / "pfCoreCatalog.ts",
    )
    print("Generated PF-Core catalog artifacts")


if __name__ == "__main__":
    main()
