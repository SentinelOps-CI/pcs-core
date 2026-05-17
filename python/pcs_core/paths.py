"""Resolve repo and schema paths for dev checkouts and installed wheels."""

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


def hash_vectors_dir() -> Path:
    return python_project_root() / "tests" / "hash_vectors"
