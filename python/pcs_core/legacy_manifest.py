"""Equivalence helpers between legacy and ReleaseManifest.v0 fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_legacy_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: manifest root must be an object")
    return data


def legacy_manifest_equivalent_to_release_manifest(
    legacy: dict[str, Any],
    release_manifest: dict[str, Any],
) -> list[str]:
    """Return human-readable drift messages (empty list means equivalent pins)."""
    errors: list[str] = []
    legacy_artifacts = legacy.get("artifacts")
    release_artifacts = release_manifest.get("artifacts")
    if not isinstance(legacy_artifacts, dict) or not isinstance(release_artifacts, dict):
        errors.append("artifacts must be objects in both manifests")
        return errors
    if set(legacy_artifacts) != set(release_artifacts):
        errors.append(
            f"artifact keys differ (legacy={sorted(legacy_artifacts)} "
            f"release={sorted(release_artifacts)})",
        )
    for name in legacy_artifacts:
        legacy_hash = legacy_artifacts[name]
        entry = release_artifacts.get(name)
        if not isinstance(entry, dict):
            errors.append(f"{name}: missing release manifest entry")
            continue
        if entry.get("sha256") != legacy_hash:
            errors.append(
                f"{name}: hash mismatch legacy={legacy_hash} release={entry.get('sha256')}",
            )
    commit_map = {
        "labtrust_gym_commit": ("labtrust_gym", "commit"),
        "certifyedge_commit": ("certifyedge", "commit"),
        "provability_fabric_commit": ("provability_fabric", "commit"),
        "scientific_memory_commit": ("scientific_memory", "commit"),
        "pcs_core_commit": ("pcs_core", "commit"),
    }
    producer_repos = release_manifest.get("producer_repos")
    if not isinstance(producer_repos, dict):
        errors.append("release manifest missing producer_repos")
        return errors
    for legacy_key, (repo_key, field) in commit_map.items():
        legacy_commit = legacy.get(legacy_key)
        repo_entry = producer_repos.get(repo_key)
        if not isinstance(repo_entry, dict):
            errors.append(f"producer_repos.{repo_key} missing")
            continue
        if repo_entry.get(field) != legacy_commit:
            errors.append(
                f"{legacy_key}: legacy {legacy_commit} != "
                f"release {repo_key}.{field} {repo_entry.get(field)}",
            )
    return errors
