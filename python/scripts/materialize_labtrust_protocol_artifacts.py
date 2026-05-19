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
    component_release_fragment_valid,
    handoff_manifest_valid,
    release_chain_validation_result_valid,
    release_manifest_valid,
    write_labtrust_protocol_artifacts,
)
from pcs_core.lean_materialize import materialize_lean_trust_artifacts  # noqa: E402
from pcs_core.release_fixtures import (  # noqa: E402
    sync_legacy_manifest_artifact_hashes,
    sync_legacy_manifest_provenance,
    sync_release_artifact_provenance,
    sync_release_chain_identity_pins,
)
from pcs_core.registry import build_artifact_registry  # noqa: E402
from pcs_core.semantic_check_execution import build_semantic_check_execution  # noqa: E402
from pcs_core.shared_hash_vectors import write_shared_vectors  # noqa: E402
from pcs_core.validate import validate_file  # noqa: E402


def main() -> int:
    release_dir = examples_dir() / "labtrust-release"
    sync_legacy_manifest_provenance(release_dir)
    sync_release_artifact_provenance(release_dir)
    sync_release_chain_identity_pins(release_dir)
    sync_legacy_manifest_artifact_hashes(release_dir)
    legacy = json.loads((release_dir / "RELEASE_FIXTURE_MANIFEST.json").read_text(encoding="utf-8"))
    pcs_commit = str(legacy.get("pcs_core_commit", ""))
    lean_digests = materialize_lean_trust_artifacts(
        release_dir,
        source_commit=pcs_commit or None,
        require_lean_build=True,
    )
    write_labtrust_protocol_artifacts(release_dir, lean_digests=lean_digests)
    examples = examples_dir()
    for name, doc in (
        (
            "release_manifest.valid.json",
            release_manifest_valid(for_examples_tree=True, lean_digests=lean_digests),
        ),
        ("handoff_manifest.valid.json", handoff_manifest_valid()),
        (
            "release_chain_validation_result.valid.json",
            release_chain_validation_result_valid(),
        ),
        ("component_release_fragment.valid.json", component_release_fragment_valid()),
        ("semantic_check_execution.valid.json", build_semantic_check_execution()),
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
