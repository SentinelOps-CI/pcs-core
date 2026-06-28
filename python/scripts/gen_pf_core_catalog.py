"""Generate PF-Core catalog artifacts from catalog/pf_core.catalog.json."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pcs_core.paths import repo_root

CATALOG_PATH = repo_root() / "catalog" / "pf_core.catalog.json"


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


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
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    return source


def generate_lean(catalog: dict, out_path: Path) -> str:
    caps = catalog["capabilities"]
    cap_ids = [cap["capability_id"] for cap in caps]
    cap_id_lines = "\n".join(f'  , "{cap}"' for cap in cap_ids[1:])
    patterns = [cap["resource_pattern"] for cap in caps]
    pattern_lines = "\n".join(
        f'  , ResourcePattern.glob "{pat}"' for pat in patterns[1:]
    )
    pattern_cases = "\n".join(
        f'  | "{cap["capability_id"]}" => "{cap["resource_pattern"]}"'
        for cap in caps
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
    cap_entries = []
    for cap in caps:
        cap_entries.append(
            f"        (\"{cap['capability_id']}\", \"{cap['effect_kind']}\", \"{cap['resource_pattern']}\"),"
        )
    role_entries = []
    for role, caps_list in role_map.items():
        items = ", ".join(f'"{c}"' for c in caps_list)
        role_entries.append(f"        (\"{role}\", &[{items}]),")
    effect_items = ", ".join(f'"{e}"' for e in effect_kinds)
    source = f'''//! Generated PF-Core catalog (do not edit by hand).

pub const EFFECT_KINDS: &[&str] = &[{effect_items}];

pub const CAPABILITY_CATALOG: &[(&str, &str, &str)] = &[
{chr(10).join(cap_entries)}
];

pub const ROLE_CAPABILITY_MAP: &[(&str, &[&str])] = &[
{chr(10).join(role_entries)}
];
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    return source


def generate_typescript(catalog: dict, out_path: Path) -> str:
    caps = catalog["capabilities"]
    role_map = catalog["role_map"]
    effect_kinds = catalog["effect_kinds"]
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
    effect_items = ", ".join(_py_repr(e) for e in effect_kinds)
    source = f'''/** Generated PF-Core catalog (do not edit by hand). */

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
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    return source


def main() -> None:
    catalog = load_catalog()
    root = repo_root()
    py_catalog = root / "python" / "pcs_core" / "pf_core_catalog.py"
    generate_python(catalog, py_catalog)
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", str(py_catalog)],
        check=True,
    )
    generate_lean(catalog, root / "lean" / "PFCore" / "Catalog.lean")
    generate_rust(catalog, root / "rust" / "crates" / "pcs-core" / "src" / "pf_core_catalog.rs")
    generate_typescript(
        catalog,
        root / "typescript" / "packages" / "core" / "src" / "pfCoreCatalog.ts",
    )
    print("Generated PF-Core catalog artifacts")


if __name__ == "__main__":
    main()
