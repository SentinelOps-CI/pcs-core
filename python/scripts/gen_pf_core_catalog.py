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

# Single source for JSON effect_kind → Lean Effect constructor terms.
# Consumed by generated Python/Rust/TS maps and Lean Catalog.lean.
EFFECT_KIND_LEAN_CONSTRUCTORS: dict[str, str] = {
    "file.read": "Effect.read",
    "file.write": "Effect.write",
    "network.egress": "Effect.network",
    "email.send": "Effect.externalMessage",
    "handoff.delegate": "Effect.stateChange",
    "mcp.invoke": "Effect.codeExecution",
    "lab.release": 'Effect.custom "lab.release"',
}


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def validate_catalog(catalog: dict) -> None:
    """Reject catalog entries whose resource patterns exceed the Lean glob subset."""
    caps = catalog.get("capabilities")
    if not isinstance(caps, list):
        raise ValueError("catalog.capabilities must be a list")
    cap_ids = {str(cap["capability_id"]) for cap in caps if isinstance(cap, dict)}
    effect_kinds = catalog.get("effect_kinds")
    if not isinstance(effect_kinds, list):
        raise ValueError("catalog.effect_kinds must be a list")
    effect_kind_set = {str(kind) for kind in effect_kinds}
    missing_constructors = sorted(effect_kind_set - set(EFFECT_KIND_LEAN_CONSTRUCTORS))
    if missing_constructors:
        raise ValueError(
            "effect_kinds missing Lean constructors in EFFECT_KIND_LEAN_CONSTRUCTORS: "
            f"{missing_constructors!r}"
        )
    for cap in caps:
        if not isinstance(cap, dict):
            raise ValueError("catalog.capabilities entries must be objects")
        pattern = str(cap.get("resource_pattern") or "")
        if _UNSUPPORTED_RESOURCE_PATTERN_RE.search(pattern):
            raise ValueError(
                f"unsupported resource_pattern for Lean glob subset: {pattern!r} "
                f"(capability {cap.get('capability_id')!r})"
            )
        effect_kind = str(cap.get("effect_kind") or "")
        if effect_kind not in effect_kind_set:
            raise ValueError(
                f"capability {cap.get('capability_id')!r} references unknown "
                f"effect_kind {effect_kind!r}"
            )
    role_map = catalog.get("role_map")
    if not isinstance(role_map, dict):
        raise ValueError("catalog.role_map must be an object")
    for role, caps_list in role_map.items():
        if not isinstance(caps_list, list):
            raise ValueError(f"role_map[{role!r}] must be a list")
        for cap_id in caps_list:
            if str(cap_id) not in cap_ids:
                raise ValueError(f"role_map[{role!r}] references unknown capability_id {cap_id!r}")
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
    workflow_modes = catalog.get("workflow_certificate_modes")
    if workflow_modes is not None:
        if not isinstance(workflow_modes, list):
            raise ValueError("catalog.workflow_certificate_modes must be a list")
        seen_workflows: set[str] = set()
        for entry in workflow_modes:
            if not isinstance(entry, dict):
                raise ValueError("catalog.workflow_certificate_modes entries must be objects")
            workflow_id = str(entry.get("workflow_id") or "")
            mode = str(entry.get("required_certificate_mode") or "")
            if not workflow_id or not mode:
                raise ValueError(f"invalid workflow_certificate_modes entry: {entry!r}")
            if workflow_id in seen_workflows:
                raise ValueError(f"duplicate workflow_certificate_modes workflow_id {workflow_id!r}")
            seen_workflows.add(workflow_id)


def _py_repr(value: object) -> str:
    return repr(value)


def _rust_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _lean_effect_term(effect_kind: str) -> str:
    mapped = EFFECT_KIND_LEAN_CONSTRUCTORS.get(effect_kind)
    if mapped is None:
        raise ValueError(f"no Lean constructor for effect_kind {effect_kind!r}")
    return mapped


def _custom_effect_labels(effect_kinds: list[str]) -> list[str]:
    labels: list[str] = []
    for kind in effect_kinds:
        term = _lean_effect_term(kind)
        if term.startswith("Effect.custom "):
            # Effect.custom "lab.release" → lab.release
            label = term[len("Effect.custom ") :].strip().strip('"')
            labels.append(label)
    return labels


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
    effect_to_lean_lines = []
    for kind in effect_kinds:
        effect_to_lean_lines.append(f"    {_py_repr(kind)}: {_py_repr(_lean_effect_term(kind))},")
    workflow_modes = catalog.get("workflow_certificate_modes") or []
    workflow_lines = []
    for entry in workflow_modes:
        workflow_lines.append(
            f"    {{"
            f'"workflow_id": {_py_repr(entry["workflow_id"])}, '
            f'"required_certificate_mode": {_py_repr(entry["required_certificate_mode"])}'
            f"}},"
        )
    workflow_block = (
        "[\n" + "\n".join(workflow_lines) + "\n]"
        if workflow_lines
        else "[]"
    )
    source = f'''"""Generated PF-Core catalog (do not edit by hand)."""

from __future__ import annotations

EFFECT_KINDS = frozenset([
    {effect_lines},
])

EFFECT_KIND_TO_LEAN: dict[str, str] = {{
{chr(10).join(effect_to_lean_lines)}
}}

CAPABILITY_CATALOG: dict[str, dict[str, str]] = {{
{chr(10).join(cap_lines)}
}}

ROLE_CAPABILITY_MAP: dict[str, list[str]] = {{
{chr(10).join(role_lines)}
}}

TOOL_NAME_MAP: dict[tuple[str, str], tuple[str, str, str]] = {{
{chr(10).join(tool_lines)}
}}

WORKFLOW_CERTIFICATE_MODES: list[dict[str, str]] = {workflow_block}
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    return source


def generate_lean(catalog: dict, out_path: Path) -> str:
    caps = catalog["capabilities"]
    role_map = catalog["role_map"]
    effect_kinds = catalog["effect_kinds"]
    tool_map = catalog["tool_map"]
    workflow_modes = catalog.get("workflow_certificate_modes") or []
    cap_ids = [cap["capability_id"] for cap in caps]
    patterns = [cap["resource_pattern"] for cap in caps]
    pattern_cases = "\n".join(
        f'  | "{cap["capability_id"]}" => "{cap["resource_pattern"]}"' for cap in caps
    )
    effect_pair_lines = "\n".join(
        f'  , ("{cap["capability_id"]}", {_lean_effect_term(cap["effect_kind"])})'
        for cap in caps[1:]
    )
    effect_ctor_cases = "\n".join(
        f'  | "{kind}" => {_lean_effect_term(kind)}' for kind in effect_kinds
    )
    custom_labels = _custom_effect_labels(effect_kinds)
    if custom_labels:
        custom_label_lines = "\n".join(f'  , "{label}"' for label in custom_labels[1:])
        custom_labels_block = (
            f'  [ "{custom_labels[0]}"\n{custom_label_lines}\n  ]'
            if len(custom_labels) > 1
            else f'  [ "{custom_labels[0]}" ]'
        )
    else:
        custom_labels_block = "  ([] : List String)"

    role_block_lines: list[str] = []
    for index, (role, caps_list) in enumerate(role_map.items()):
        caps_lit = ", ".join(f'"{c}"' for c in caps_list)
        prefix = "      " if index == 0 else "      , "
        role_block_lines.append(f'{prefix}("{role}", [{caps_lit}])')
    role_block = "\n".join(role_block_lines)

    tool_lines = []
    for index, entry in enumerate(tool_map):
        prefix = "  [" if index == 0 else "  ,"
        tool_lines.append(
            f'{prefix} ("{entry["tool_name"]}", "{entry["tool_category"]}", '
            f'"{entry["capability_id"]}")'
        )
    if tool_lines:
        tool_lines.append("  ]")
        tool_block = "\n".join(tool_lines)
    else:
        tool_block = "  ([] : List (String × String × String))"

    workflow_lines = []
    for index, entry in enumerate(workflow_modes):
        prefix = "  [" if index == 0 else "  ,"
        workflow_lines.append(
            f'{prefix} ("{entry["workflow_id"]}", "{entry["required_certificate_mode"]}")'
        )
    if workflow_lines:
        workflow_lines.append("  ]")
        workflow_block = "\n".join(workflow_lines)
    else:
        workflow_block = "  ([] : List (String × String))"

    effect_kind_lines = "\n".join(f'  , "{kind}"' for kind in effect_kinds[1:])

    source = f'''import PFCore.Effect

/-!
# PF-Core generated catalog (do not edit by hand).

Emits capability ids, resource patterns, capability→effect mappings, effect
constructors, role map, tool map, and workflow certificate modes from
`catalog/pf_core.catalog.json`.
-/

namespace PFCore.Catalog
open PFCore

def knownCatalogCaps : List String :=
  [ "{cap_ids[0]}"
{chr(10).join(f'  , "{cap}"' for cap in cap_ids[1:])}
  ]

def catalogResourcePatternStrings : List String :=
  [ "{patterns[0]}"
{chr(10).join(f'  , "{pat}"' for pat in patterns[1:])}
  ]

def capabilityPatternString (cap : String) : String :=
  match cap with
{pattern_cases}
  | _ => ""

/-- Catalog pairs mapping capability ids to canonical embedded effects. -/
def knownCapabilityEffectCatalog : List (String × Effect) :=
  [ ("{caps[0]["capability_id"]}", {_lean_effect_term(caps[0]["effect_kind"])})
{effect_pair_lines}
  ]

/-- JSON effect_kind string → Lean ``Effect`` constructor. -/
def effectKindToEffect (kind : String) : Effect :=
  match kind with
{effect_ctor_cases}
  | other => Effect.custom other

/-- Custom effect labels admitted by ``EffectKnown``. -/
def knownCustomEffectLabels : List String :=
{custom_labels_block}

/-- Closed effect_kind vocabulary from the catalog JSON. -/
def knownEffectKindStrings : List String :=
  [ "{effect_kinds[0]}"
{effect_kind_lines}
  ]

/-- Runtime role → capability entries (mirrors Python ``ROLE_CAPABILITY_MAP``). -/
def runtimeRoleMapEntries : List (String × List String) :=
  [
{role_block}
  ]

/-- Tool name/category → capability id triples. -/
def toolMapEntries : List (String × String × String) :=
{tool_block}

/-- Workflow id → required certificate mode. -/
def workflowCertificateModeEntries : List (String × String) :=
{workflow_block}

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
    effect_lean_entries = []
    for kind in effect_kinds:
        effect_lean_entries.append(
            f"        ({_rust_string(kind)}, {_rust_string(_lean_effect_term(kind))}),"
        )
    workflow_modes = catalog.get("workflow_certificate_modes") or []
    workflow_entries = []
    for entry in workflow_modes:
        workflow_entries.append(
            f'        ("{entry["workflow_id"]}", "{entry["required_certificate_mode"]}"),'
        )
    workflow_block = ""
    if workflow_entries:
        workflow_block = f"""

pub const WORKFLOW_CERTIFICATE_MODES: &[(&str, &str)] = &[
{chr(10).join(workflow_entries)}
];
"""
    source = f"""//! Generated PF-Core catalog (do not edit by hand).

pub const EFFECT_KINDS: &[&str] = &[{effect_items}];

pub const EFFECT_KIND_TO_LEAN: &[(&str, &str)] = &[
{chr(10).join(effect_lean_entries)}
];

pub const CAPABILITY_CATALOG: &[(&str, &str, &str)] = &[
{chr(10).join(cap_entries)}
];

pub const ROLE_CAPABILITY_MAP: &[(&str, &[&str])] = &[
{chr(10).join(role_entries)}
];

pub const TOOL_NAME_MAP: &[(&str, &str, &str, &str, &str)] = &[
{chr(10).join(tool_entries)}
];{workflow_block}"""
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
    effect_lean_lines = []
    for kind in effect_kinds:
        effect_lean_lines.append(
            f"  {_py_repr(kind)}: {_py_repr(_lean_effect_term(kind))},"
        )
    workflow_modes = catalog.get("workflow_certificate_modes") or []
    workflow_lines = []
    for entry in workflow_modes:
        workflow_lines.append(
            f"  {{ workflow_id: {_py_repr(entry['workflow_id'])}, "
            f"required_certificate_mode: {_py_repr(entry['required_certificate_mode'])} }},"
        )
    workflow_block = ""
    if workflow_lines:
        workflow_block = (
            "\n\nexport const WORKFLOW_CERTIFICATE_MODES: ReadonlyArray<{\n"
            "  workflow_id: string;\n"
            "  required_certificate_mode: string;\n"
            "}> = [\n"
            + "\n".join(workflow_lines)
            + "\n];"
        )
    source = f"""/** Generated PF-Core catalog (do not edit by hand). */

export const EFFECT_KINDS = new Set<string>([{effect_items}]);

export const EFFECT_KIND_TO_LEAN: Record<string, string> = {{
{chr(10).join(effect_lean_lines)}
}};

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
}};{workflow_block}
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
