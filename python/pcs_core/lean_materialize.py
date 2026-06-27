"""Write ProofObligation.v0 and LeanCheckResult.v0 into a release fixture directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.lean_trust import run_lean_check, write_proof_obligations_for_release
from pcs_core.release_fixtures import file_digest
from pcs_core.validate import validate_file


def materialize_lean_trust_artifacts(
    release_dir: Path,
    *,
    source_commit: str | None = None,
    require_lean_build: bool = True,
    skip_if_unchanged: bool = False,
) -> dict[str, str]:
    """Emit proof_obligation.v0.json and lean_check_result.v0.json; return path -> sha256."""
    release_dir = release_dir.resolve()
    obligation_path = release_dir / "proof_obligation.v0.json"
    check_path = release_dir / "lean_check_result.v0.json"

    if skip_if_unchanged and obligation_path.is_file() and check_path.is_file():
        try:
            validate_file(obligation_path)
            validate_file(check_path)
            return {
                str(obligation_path.name): file_digest(obligation_path.read_bytes()),
                str(check_path.name): file_digest(check_path.read_bytes()),
            }
        except Exception:
            pass

    write_proof_obligations_for_release(release_dir, obligation_path)
    obligations = json.loads(obligation_path.read_text(encoding="utf-8"))
    result = run_lean_check(
        obligations,
        source_commit=source_commit,
        require_lean_build=require_lean_build,
    )
    if result.get("status") != "ProofChecked":
        raise ValueError(
            f"lean-check rejected for {release_dir}: {result.get('failure_reason')}",
        )
    check_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    validate_file(obligation_path)
    validate_file(check_path)
    return {
        obligation_path.name: file_digest(obligation_path.read_bytes()),
        check_path.name: file_digest(check_path.read_bytes()),
    }


def patch_release_manifest_lean_refs(release_dir: Path, *, source_commit: str) -> dict[str, str]:
    """Materialize lean artifacts and merge optional refs into release_manifest.v0.json."""
    from pcs_core.hash import canonical_hash

    release_dir = release_dir.resolve()
    lean_digests = materialize_lean_trust_artifacts(
        release_dir,
        source_commit=source_commit,
        require_lean_build=False,
    )
    manifest_path = release_dir / "release_manifest.v0.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"{manifest_path} not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path}: root must be an object")
    manifest.update(lean_trust_manifest_refs(lean_digests))
    manifest["signature_or_digest"] = canonical_hash(
        {k: v for k, v in manifest.items() if k != "signature_or_digest"},
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return lean_digests


def lean_trust_manifest_refs(digests: dict[str, str]) -> dict[str, Any]:
    """ReleaseManifest.v0 optional fields for formal-check artifacts."""
    refs: dict[str, Any] = {}
    if "proof_obligation.v0.json" in digests:
        refs["proof_obligation"] = {
            "path": "proof_obligation.v0.json",
            "sha256": digests["proof_obligation.v0.json"],
        }
    if "lean_check_result.v0.json" in digests:
        refs["lean_check_result"] = {
            "path": "lean_check_result.v0.json",
            "sha256": digests["lean_check_result.v0.json"],
        }
    return refs
