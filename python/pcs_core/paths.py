"""Resolve repo and schema paths for dev checkouts and installed wheels.

Lean roots, kernel sources, generated proofs, pins, and catalogs are resolved
by :mod:`pcs_core.asset_resolver` (authoritative for verifier assets).
"""

from __future__ import annotations

from pathlib import Path


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def python_project_root() -> Path:
    return package_dir().parent


def repo_root() -> Path:
    return python_project_root().parent


def schemas_dir() -> Path:
    bundled = package_dir() / "schemas"
    if bundled.is_dir() and any(bundled.glob("*.json")):
        return bundled
    checkout = repo_root() / "schemas"
    if checkout.is_dir():
        return checkout
    raise FileNotFoundError(
        "PCS schemas not found. Install pcs-core from a release wheel or use a full checkout."
    )


def examples_dir() -> Path:
    return repo_root() / "examples"


RELEASE_FIXTURE_MANIFEST = "RELEASE_FIXTURE_MANIFEST.json"


def resolve_release_chain_directory(path: Path) -> Path:
    """Resolve release-chain dir from cwd or pcs-core repo root.

    When ``pcs`` runs from ``python/``, ``examples/labtrust-release`` is
    retried under :func:`repo_root` if the cwd-relative path has no manifest.
    """
    if path.is_file() and path.name == RELEASE_FIXTURE_MANIFEST:
        directory = path.parent
    else:
        directory = path

    def has_manifest(candidate: Path) -> bool:
        return (candidate / RELEASE_FIXTURE_MANIFEST).is_file()

    resolved = directory.resolve()
    if has_manifest(resolved):
        return resolved

    if not directory.is_absolute():
        from_root = (repo_root() / directory).resolve()
        if has_manifest(from_root):
            return from_root

    return resolved


def hash_vectors_dir() -> Path:
    return python_project_root() / "tests" / "hash_vectors"
