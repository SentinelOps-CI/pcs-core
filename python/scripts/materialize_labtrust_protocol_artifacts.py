#!/usr/bin/env python3
"""Write Phase 2 protocol artifacts into examples/labtrust-release/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from pcs_core.paths import examples_dir  # noqa: E402
from pcs_core.protocol_fixtures import (  # noqa: E402
    handoff_manifest_valid,
    release_chain_validation_result_valid,
    release_manifest_valid,
    write_labtrust_protocol_artifacts,
)
from pcs_core.registry import build_artifact_registry  # noqa: E402
from pcs_core.shared_hash_vectors import write_shared_vectors  # noqa: E402
from pcs_core.validate import validate_file  # noqa: E402


def main() -> int:
    release_dir = examples_dir() / "labtrust-release"
    write_labtrust_protocol_artifacts(release_dir)
    examples = examples_dir()
    for name, doc in (
        ("release_manifest.valid.json", release_manifest_valid()),
        ("handoff_manifest.valid.json", handoff_manifest_valid()),
        (
            "release_chain_validation_result.valid.json",
            release_chain_validation_result_valid(),
        ),
    ):
        (examples / name).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    registry_path = examples_dir() / "artifact_registry.valid.json"
    registry_path.write_text(
        json.dumps(build_artifact_registry(), indent=2) + "\n",
        encoding="utf-8",
    )
    for path in sorted(release_dir.glob("*.v0.json")):
        validate_file(path)
    validate_file(registry_path)
    write_shared_vectors(force=True)
    print(f"Wrote protocol artifacts under {release_dir}")
    print("Refreshed test_vectors/hash/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
