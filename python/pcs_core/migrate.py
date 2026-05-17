"""PCS artifact migration helpers (v0.1 baseline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.validate import ValidationError, detect_artifact_type, validate_artifact


def migrate_artifact(
    data: dict[str, Any],
    *,
    from_version: str,
    to_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return migrated artifact and a migration report."""
    if from_version != "v0" or to_version != "v0":
        raise ValidationError(
            f"Only v0->v0 identity migration is implemented in pcs-core 0.1.0 "
            f"(requested {from_version} -> {to_version})",
        )
    artifact_type = detect_artifact_type(data)
    if not artifact_type:
        raise ValidationError("Could not detect artifact type for migration")
    validate_artifact(data, artifact_type)
    report = {
        "from_version": from_version,
        "to_version": to_version,
        "artifact_type": artifact_type,
        "changes": [],
        "status": "noop",
    }
    return dict(data), report


def migrate_file(path: Path, *, from_version: str, to_version: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: artifact root must be a JSON object")
    migrated, report = migrate_artifact(data, from_version=from_version, to_version=to_version)
    report["source_path"] = str(path)
    if migrated != data:
        path.write_text(json.dumps(migrated, indent=2) + "\n", encoding="utf-8")
        report["status"] = "migrated"
    return report
