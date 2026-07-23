"""Honest runtime capability detection for validator vs verifier installs."""

from __future__ import annotations

import importlib.util
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from pcs_core.asset_resolver import lean_root as resolve_lean_root
from pcs_core.asset_resolver import resolver_report
from pcs_core.paths import package_dir, repo_root

CAPABILITY_KEYS = (
    "schema_validation",
    "rust_validator",
    "typescript_validator",
    "lean_toolchain",
    "pf_core_kernel",
    "pcs_envelope_kernel",
    "live_certifyedge",
)


def _schemas_available() -> bool:
    try:
        from pcs_core.paths import schemas_dir

        root = schemas_dir()
        return root.is_dir() and any(root.glob("*.json"))
    except FileNotFoundError:
        return False


def _jsonschema_available() -> bool:
    return importlib.util.find_spec("jsonschema") is not None


def _lean_checkout_dir() -> Path | None:
    """Locate Lean project sources (checkout or wheel-bundled verifier assets)."""
    root = resolve_lean_root()
    if root is not None and (root / "lakefile.lean").is_file():
        return root
    return None


def _lake_available() -> bool:
    if shutil.which("lake"):
        return True
    if platform.system() == "Windows" and shutil.which("wsl"):
        # Presence of WSL is not enough; require lake inside WSL.
        proc = shutil.which("wsl")
        if not proc:
            return False
        import subprocess

        try:
            result = subprocess.run(
                ["wsl", "bash", "-lc", "command -v lake"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0 and bool(result.stdout.strip())
    return False


def _rust_validator_available() -> bool:
    if shutil.which("pcs-core") or shutil.which("pcs_validate"):
        return True
    crate = repo_root() / "rust" / "crates" / "pcs-core"
    return crate.is_dir() and shutil.which("cargo") is not None


def _typescript_validator_available() -> bool:
    pkg = repo_root() / "typescript" / "packages" / "core"
    if not pkg.is_dir():
        return False
    if not (shutil.which("node") and shutil.which("npm")):
        return False
    # Prefer a built package; fall back to sources that `npm test` can exercise.
    dist = pkg / "dist"
    src = pkg / "src"
    return dist.is_dir() or src.is_dir()


def _pf_core_kernel_available(lean_root: Path | None) -> bool:
    if lean_root is None:
        return False
    return (lean_root / "PFCore" / "Basic.lean").is_file() or (lean_root / "PFCore.lean").is_file()


def _pcs_envelope_kernel_available(lean_root: Path | None) -> bool:
    if lean_root is None:
        return False
    return (lean_root / "PCS" / "Basic.lean").is_file() or (lean_root / "PCS.lean").is_file()


def _live_certifyedge_available() -> bool:
    from pcs_core.pf_core_certifyedge import certifyedge_cli_available

    return certifyedge_cli_available()


def detect_capabilities() -> dict[str, Any]:
    """Detect which PCS products and backends are actually usable here."""
    lean_root = _lean_checkout_dir()
    schema_ok = _schemas_available() and _jsonschema_available()
    lake_ok = _lake_available()
    pf_core_ok = _pf_core_kernel_available(lean_root)
    pcs_env_ok = _pcs_envelope_kernel_available(lean_root)
    verifier_assets = lean_root is not None and pf_core_ok and pcs_env_ok

    caps = {
        "schema_validation": schema_ok,
        "rust_validator": _rust_validator_available(),
        "typescript_validator": _typescript_validator_available(),
        "lean_toolchain": lake_ok,
        "pf_core_kernel": pf_core_ok and lake_ok,
        "pcs_envelope_kernel": pcs_env_ok and lake_ok,
        "live_certifyedge": _live_certifyedge_available(),
    }

    product = "verifier" if verifier_assets and lake_ok else "validator"
    notes: list[str] = []
    if product == "validator":
        notes.append(
            "Validator distribution: schema and semantic validation only. "
            "Lean verification is not advertised because verifier assets or "
            "the Lean toolchain are absent."
        )
    if lean_root is not None and not lake_ok:
        notes.append(
            "Lean sources are present but `lake` is not available on PATH "
            "(or via WSL). Install the pinned Lean toolchain before claiming "
            "kernel verification."
        )
    if caps["pf_core_kernel"] is False and pf_core_ok and not lake_ok:
        notes.append("PF-Core Lean sources found; toolchain required for lean-check.")
    if not caps["live_certifyedge"]:
        notes.append(
            "Live CertifyEdge CLI not detected. Mock/stub modes remain for "
            "dev format checks only and are not release attestations."
        )

    assets = resolver_report()
    return {
        "product": product,
        "version": _package_version(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "capabilities": caps,
        "paths": {
            "package_dir": str(package_dir()),
            "lean_dir": str(lean_root) if lean_root else None,
            "distribution_root": assets.get("distribution_root"),
            "pins_dir": assets.get("pins_dir"),
            "catalog_dir": assets.get("catalog_dir"),
            "schemas_available": schema_ok,
        },
        "notes": notes,
    }


def _package_version() -> str:
    try:
        from pcs_core import __version__

        return str(__version__)
    except Exception:
        return "unknown"


def format_capabilities_report(report: dict[str, Any] | None = None) -> str:
    data = report or detect_capabilities()
    caps: dict[str, bool] = dict(data.get("capabilities") or {})
    lines = [
        f"pcs product: {data.get('product')}",
        f"pcs version: {data.get('version')}",
        f"python: {data.get('python')}",
        "",
        "capabilities:",
        f"  schema validation available: {_yn(caps.get('schema_validation'))}",
        f"  Rust validator available: {_yn(caps.get('rust_validator'))}",
        f"  TypeScript validator available: {_yn(caps.get('typescript_validator'))}",
        f"  Lean toolchain available: {_yn(caps.get('lean_toolchain'))}",
        f"  PF-Core kernel available: {_yn(caps.get('pf_core_kernel'))}",
        f"  PCS envelope kernel available: {_yn(caps.get('pcs_envelope_kernel'))}",
        f"  live CertifyEdge available: {_yn(caps.get('live_certifyedge'))}",
    ]
    notes = data.get("notes") or []
    if notes:
        lines.append("")
        lines.append("notes:")
        for note in notes:
            lines.append(f"  - {note}")
    return "\n".join(lines) + "\n"


def _yn(value: bool | None) -> str:
    return "yes" if value else "no"


def cmd_capabilities(*, as_json: bool = False) -> int:
    report = detect_capabilities()
    if as_json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_capabilities_report(report))
    return 0
