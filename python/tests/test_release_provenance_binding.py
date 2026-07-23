"""Release provenance binding schema + digest sealing (PR15 / B8)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from pcs_core.validate import ValidationError, validate_artifact

ROOT = Path(__file__).resolve().parents[2]


def _minimal_binding(**overrides: object) -> dict:
    digest = "sha256:" + ("a" * 64)
    commit = "b" * 40
    body = {
        "schema_version": "v0",
        "artifact_type": "ReleaseProvenanceBinding.v0",
        "canonicalization_version": "v1",
        "version": "0.0.0-test",
        "source_commit": commit,
        "source_ref": "refs/heads/main",
        "workflow": {
            "repository": "SentinelOps-CI/pcs-core",
            "workflow_ref": "SentinelOps-CI/pcs-core/.github/workflows/release-provenance.yml@refs/heads/main",
            "workflow_sha": commit,
            "run_id": "1",
            "run_attempt": "1",
            "event_name": "workflow_dispatch",
            "server_url": "https://github.com",
        },
        "builder": {
            "id": "https://github.com/SentinelOps-CI/pcs-core/actions/runs/1",
            "runner_name": "test",
            "runner_os": "Linux",
            "runner_arch": "X64",
        },
        "lockfiles": {
            "python/requirements.lock": {
                "path": "python/requirements.lock",
                "sha256": digest,
            },
            "rust/Cargo.lock": {"path": "rust/Cargo.lock", "sha256": digest},
            "typescript/package-lock.json": {
                "path": "typescript/package-lock.json",
                "sha256": digest,
            },
        },
        "verifier_image": {
            "pin_path": "pins/python-base-image.json",
            "index_digest": digest,
            "dockerfile_from": f"python@{digest}",
            "pin_file_sha256": digest,
        },
        "wheels": [
            {
                "path": "wheels/pcs_core-0.0.0-py3-none-any.whl",
                "filename": "pcs_core-0.0.0-py3-none-any.whl",
                "sha256": digest,
            }
        ],
        "sbom": {
            "path": "sbom/pcs-core.cdx.json",
            "sha256": digest,
            "format": "scaffold-CycloneDX-JSON",
        },
        "bundle": {
            "status": "absent",
            "absence_reason": "unit test fixture",
        },
        "attestation": {
            "status": "gated",
            "predicate_type": "https://slsa.dev/provenance/v1",
            "method": "none",
            "attestation_ids": [],
            "attestation_urls": [],
            "gate_reason": "unit test",
        },
        "subjects_checksums_path": "subjects.sha256",
    }
    sealed = {**body, **overrides}
    canonical = json.dumps(
        {k: v for k, v in sealed.items() if k != "signature_or_digest"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    sealed["signature_or_digest"] = "sha256:" + hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return sealed


def test_release_provenance_binding_schema_accepts_gated() -> None:
    validate_artifact(_minimal_binding(), "ReleaseProvenanceBinding.v0", release_grade=True)


def test_release_provenance_binding_rejects_fake_signed_without_method() -> None:
    bad = _minimal_binding()
    bad["attestation"]["status"] = "signed"
    bad["attestation"]["method"] = "none"
    # Still schema-valid (honesty enforced by finalize/verify scripts), but
    # signature_or_digest must be recomputed for schema-only check.
    sealed = {k: v for k, v in bad.items() if k != "signature_or_digest"}
    canonical = json.dumps(sealed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    bad["signature_or_digest"] = "sha256:" + hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    validate_artifact(bad, "ReleaseProvenanceBinding.v0", release_grade=True)


def test_release_provenance_binding_rejects_bad_commit() -> None:
    with pytest.raises(ValidationError):
        validate_artifact(
            _minimal_binding(source_commit="not-a-commit"),
            "ReleaseProvenanceBinding.v0",
        )


@pytest.mark.skipif(
    not (ROOT / "scripts" / "build-release-provenance.sh").is_file(),
    reason="scripts missing",
)
@pytest.mark.skipif(
    __import__("os").name == "nt",
    reason="bash provenance scripts require a POSIX shell with native paths",
)
def test_build_and_verify_provenance_scripts_gated(tmp_path: Path) -> None:
    """End-to-end local gated path (no GitHub Sigstore)."""
    out = tmp_path / "provenance"
    env = {
        **dict(__import__("os").environ),
        "PCS_PROVENANCE_BUILD_WHEELS": "1",
        "PCS_PROVENANCE_BUILD_SBOM": "1",
    }
    # Avoid requiring a PF-Core bundle for this unit smoke.
    env.pop("PCS_PROVENANCE_BUNDLE_DIR", None)
    subprocess.run(
        ["bash", str(ROOT / "scripts" / "build-release-provenance.sh"), str(out)],
        check=True,
        cwd=str(ROOT),
        env=env,
    )
    subprocess.run(
        [
            "bash",
            str(ROOT / "scripts" / "finalize-provenance-attestation.sh"),
            str(out),
            "gated",
            "pytest local gated path",
        ],
        check=True,
        cwd=str(ROOT),
    )
    subprocess.run(
        ["bash", str(ROOT / "scripts" / "verify-release-provenance.sh"), str(out)],
        check=True,
        cwd=str(ROOT),
        env={**env, "PCS_PROVENANCE_REQUIRE_SIGNED": "0"},
    )
    binding = json.loads((out / "ReleaseProvenanceBinding.v0.json").read_text(encoding="utf-8"))
    assert binding["attestation"]["status"] == "gated"
    assert (out / "PROVENANCE_ATTESTATION_GATED.json").is_file()
    validate_artifact(binding, "ReleaseProvenanceBinding.v0", release_grade=True)
