"""Authoritative resolver for PCS / PF-Core distribution assets.

Every compiler, hash, bundle, and proof-reference path must resolve Lean roots,
kernel sources, generated-proof directories, pins, and catalogs through this
module instead of hardcoding ``repo_root() / \"lean\"`` (or equivalent).

Resolution order (highest precedence first):

1. Explicit environment overrides (``PCS_DISTRIBUTION_ROOT``, ``PCS_LEAN_ROOT``,
   ``PCS_PINS_DIR``, ``PCS_CATALOG_DIR``).
2. Verifier-wheel layout: assets bundled under ``package_dir()``
   (``pcs_core/lean``, ``pcs_core/pins``, ``pcs_core/catalog``).
3. Developer checkout: assets under ``repo_root()``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pcs_core.paths import package_dir, repo_root, schemas_dir

__all__ = [
    "ENV_CATALOG_DIR",
    "ENV_DISTRIBUTION_ROOT",
    "ENV_LEAN_ROOT",
    "ENV_PINS_DIR",
    "catalog_dir",
    "distribution_root",
    "lean_root",
    "pcs_generated_root",
    "pcs_kernel_root",
    "pf_core_generated_root",
    "pf_core_kernel_root",
    "pin_path",
    "pins_dir",
    "proof_ref_from_path",
    "relative_to_distribution",
    "require_lean_root",
    "resolver_report",
    "schemas_dir",
]

ENV_DISTRIBUTION_ROOT = "PCS_DISTRIBUTION_ROOT"
ENV_LEAN_ROOT = "PCS_LEAN_ROOT"
ENV_PINS_DIR = "PCS_PINS_DIR"
ENV_CATALOG_DIR = "PCS_CATALOG_DIR"


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _is_lean_project(path: Path) -> bool:
    return path.is_dir() and (path / "lakefile.lean").is_file()


def _has_pins(path: Path) -> bool:
    return path.is_dir() and (path / "elan.json").is_file()


def _has_catalog(path: Path) -> bool:
    return path.is_dir() and (path / "pf_core.catalog.json").is_file()


def distribution_root() -> Path | None:
    """Return the root that owns ``lean/``, ``pins/``, and ``catalog/``.

    Returns ``None`` when neither a verifier-wheel layout nor a checkout is
    detectable (validator-only installs without Lean assets).
    """
    override = _env_path(ENV_DISTRIBUTION_ROOT)
    if override is not None:
        return override if override.is_dir() else None

    bundled_lean = package_dir() / "lean"
    if _is_lean_project(bundled_lean):
        return package_dir()

    checkout_lean = repo_root() / "lean"
    if _is_lean_project(checkout_lean):
        return repo_root()

    # Pins / catalog alone (validator wheel) still define a distribution root.
    if _has_pins(package_dir() / "pins") or _has_catalog(package_dir() / "catalog"):
        return package_dir()
    if _has_pins(repo_root() / "pins") or _has_catalog(repo_root() / "catalog"):
        return repo_root()
    return None


def lean_root(*, required: bool = False) -> Path | None:
    """Locate the Lake project root (contains ``lakefile.lean``)."""
    override = _env_path(ENV_LEAN_ROOT)
    if override is not None:
        if _is_lean_project(override):
            return override
        if required:
            raise FileNotFoundError(
                f"{ENV_LEAN_ROOT}={override} is not a Lean project (missing lakefile.lean)"
            )
        return None

    dist = distribution_root()
    if dist is not None:
        candidate = dist / "lean"
        if _is_lean_project(candidate):
            return candidate

    # Fall back to the historical checkout layout even when lakefile is absent
    # so callers that only need a Path keep working in incomplete trees.
    fallback = repo_root() / "lean"
    if _is_lean_project(fallback):
        return fallback
    if required:
        raise FileNotFoundError(
            "Lean project not found. Install the verifier wheel / OCI image, "
            f"set {ENV_LEAN_ROOT}, or use a full pcs-core checkout."
        )
    return None if not fallback.exists() else fallback


def require_lean_root() -> Path:
    """Return the Lean project root or raise ``FileNotFoundError``."""
    root = lean_root(required=True)
    assert root is not None
    return root


def pf_core_kernel_root() -> Path:
    """PF-Core kernel sources (excludes write target under Generated/)."""
    return require_lean_root() / "PFCore"


def pcs_kernel_root() -> Path:
    """PCS envelope kernel sources."""
    return require_lean_root() / "PCS"


def pf_core_generated_root() -> Path:
    """Directory for generated PF-Core proof modules."""
    return pf_core_kernel_root() / "Generated"


def pcs_generated_root() -> Path:
    """Directory for generated PCS envelope proof modules."""
    return pcs_kernel_root() / "Generated"


def pins_dir(*, required: bool = False) -> Path | None:
    """Locate the supply-chain pins directory."""
    override = _env_path(ENV_PINS_DIR)
    if override is not None:
        if _has_pins(override) or override.is_dir():
            return override
        if required:
            raise FileNotFoundError(f"{ENV_PINS_DIR}={override} is not a pins directory")
        return None

    for candidate in (
        package_dir() / "pins",
        (distribution_root() or Path()) / "pins",
        repo_root() / "pins",
    ):
        if candidate == Path("pins"):
            continue
        if _has_pins(candidate):
            return candidate

    if required:
        raise FileNotFoundError(
            "pins/ not found. Install pcs-core with pins embedded or use a full checkout."
        )
    return None


def pin_path(name: str, *, required: bool = True) -> Path | None:
    """Resolve a pin file such as ``elan.json`` or ``python-base-image.json``.

    When ``required`` is False, returns ``None`` if the pins directory or file
    is absent instead of raising.
    """
    filename = name if name.endswith(".json") else f"{name}.json"
    root = pins_dir(required=False)
    if root is None:
        if required:
            raise FileNotFoundError(f"pins directory unavailable for {filename}")
        return None
    path = root / filename
    if not path.is_file():
        if required:
            raise FileNotFoundError(f"pin file not found: {path}")
        return None
    return path


def catalog_dir(*, required: bool = False) -> Path | None:
    """Locate the PF-Core / domain catalog directory."""
    override = _env_path(ENV_CATALOG_DIR)
    if override is not None:
        if _has_catalog(override) or override.is_dir():
            return override
        if required:
            raise FileNotFoundError(f"{ENV_CATALOG_DIR}={override} is not a catalog directory")
        return None

    for candidate in (
        package_dir() / "catalog",
        (distribution_root() or Path()) / "catalog",
        repo_root() / "catalog",
    ):
        if candidate == Path("catalog"):
            continue
        if _has_catalog(candidate):
            return candidate

    if required:
        raise FileNotFoundError(
            "catalog/ not found. Install pcs-core from a release wheel or use a full checkout."
        )
    return None


def relative_to_distribution(path: Path) -> str:
    """Return a stable posix-relative asset path for digests and proof refs.

    Prefers ``distribution_root()``; falls back to ``repo_root()``; finally
    returns the absolute path with forward slashes when the file lives outside
    either root (ephemeral temp proofs).
    """
    resolved = path.resolve()
    for root in (distribution_root(), repo_root()):
        if root is None:
            continue
        try:
            return resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    lean = lean_root()
    if lean is not None:
        try:
            rel = resolved.relative_to(lean.resolve()).as_posix()
            return f"lean/{rel}"
        except ValueError:
            pass
    return str(resolved).replace("\\", "/")


def proof_ref_from_path(path: Path) -> str:
    """Stable proof_term_ref for a generated Lean file."""
    return relative_to_distribution(path)


def resolver_report() -> dict[str, Any]:
    """Machine-readable summary of resolved asset locations."""
    lean = lean_root()
    pins = pins_dir()
    catalog = catalog_dir()
    try:
        schemas = str(schemas_dir())
        schemas_ok = True
    except FileNotFoundError:
        schemas = None
        schemas_ok = False
    return {
        "distribution_root": str(distribution_root()) if distribution_root() else None,
        "lean_root": str(lean) if lean else None,
        "pf_core_kernel_root": str(lean / "PFCore") if lean else None,
        "pcs_kernel_root": str(lean / "PCS") if lean else None,
        "pf_core_generated_root": str(lean / "PFCore" / "Generated") if lean else None,
        "pcs_generated_root": str(lean / "PCS" / "Generated") if lean else None,
        "pins_dir": str(pins) if pins else None,
        "catalog_dir": str(catalog) if catalog else None,
        "schemas_dir": schemas,
        "schemas_available": schemas_ok,
        "lean_project_present": bool(lean and _is_lean_project(lean)),
        "pf_core_kernel_present": bool(
            lean
            and ((lean / "PFCore" / "Basic.lean").is_file() or (lean / "PFCore.lean").is_file())
        ),
        "pcs_kernel_present": bool(
            lean and ((lean / "PCS" / "Basic.lean").is_file() or (lean / "PCS.lean").is_file())
        ),
    }
