"""Generate and verify PCS v0.1 LabTrust release fixture bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pcs_core.paths import examples_dir, repo_root
from pcs_core.validate import ValidationError, validate_file

RELEASE_DIR_NAME = "labtrust-release"
CONFORMANCE_DIR_NAME = "labtrust"
MANIFEST_NAME = "RELEASE_FIXTURE_MANIFEST.json"

RELEASE_PCS_ARTIFACTS = (
    "runtime_receipt.json",
    "trace_certificate.json",
    "science_claim_bundle.pending.json",
    "science_claim_bundle.certified.json",
    "verification_result.json",
    "signed_science_claim_bundle.json",
)

CHAIN_ARTIFACTS = (
    "trace.json",
    *RELEASE_PCS_ARTIFACTS,
)

MANIFEST_ARTIFACTS = (
    *CHAIN_ARTIFACTS,
    "scientific_memory_import_report.json",
)

COMMIT_KEYS = (
    "pcs_core_commit",
    "labtrust_gym_commit",
    "certifyedge_commit",
    "provability_fabric_commit",
    "scientific_memory_commit",
)

PLACEHOLDER_COMMIT_RE = re.compile(r"^(?:a{40}|b{40}|c{40}|d{40}|e{40}|0{40})$")

SIBLING_REPOS: dict[str, str] = {
    "labtrust_gym_commit": "LabTrust-Gym",
    "certifyedge_commit": "CertifyEdge",
    "provability_fabric_commit": "provability-fabric",
    "scientific_memory_commit": "scientific-memory",
}

DEFAULT_CLAIM_ID = "claim-pcs-qc-release-v0.1"


def release_dir() -> Path:
    return examples_dir() / RELEASE_DIR_NAME


def conformance_dir() -> Path:
    return examples_dir() / CONFORMANCE_DIR_NAME


def file_digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def write_json(path: Path, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def is_placeholder_commit(commit: str) -> bool:
    return bool(PLACEHOLDER_COMMIT_RE.fullmatch(commit.strip()))


def git_commit_at(path: Path) -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=path,
                text=True,
            )
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "0000000000000000000000000000000000000000"


def git_commit_or(env_key: str, repo_path: Path) -> str:
    value = os.environ.get(env_key, "").strip()
    if value:
        return value
    return git_commit_at(repo_path)


def resolve_five_repo_commits() -> dict[str, str]:
    parent = repo_root().parent
    return {
        "pcs_core_commit": git_commit_or("PCS_CORE_COMMIT", repo_root()),
        "labtrust_gym_commit": git_commit_or("LABTRUST_GYM_COMMIT", parent / "LabTrust-Gym"),
        "certifyedge_commit": git_commit_or("CERTIFYEDGE_COMMIT", parent / "CertifyEdge"),
        "provability_fabric_commit": git_commit_or(
            "PROVABILITY_FABRIC_COMMIT",
            parent / "provability-fabric",
        ),
        "scientific_memory_commit": git_commit_or(
            "SCIENTIFIC_MEMORY_COMMIT",
            parent / "scientific-memory",
        ),
    }


def resolve_chain_workdir() -> Path:
    if env_work := os.environ.get("PCS_CHAIN_WORK", "").strip():
        work = Path(env_work)
        if work.is_dir():
            return work
        raise FileNotFoundError(f"PCS_CHAIN_WORK is not a directory: {work}")

    default = repo_root().parent / "LabTrust-Gym"
    if _chain_artifacts_present(default):
        return default

    raise FileNotFoundError(
        "No cross-repo chain workdir found. Run the PCS v0.1 clean-checkout chain "
        "(LabTrust-Gym examples/pcs_qc_release/scripts/run_pcs_v01_clean_chain) "
        "or set PCS_CHAIN_WORK to the directory containing chain outputs."
    )


def _chain_artifacts_present(workdir: Path) -> bool:
    return all((workdir / name).is_file() for name in CHAIN_ARTIFACTS)


def resolve_sm_import_report(workdir: Path, *, claim_id: str = DEFAULT_CLAIM_ID) -> Path:
    if env_path := os.environ.get("SCIENTIFIC_MEMORY_IMPORT_REPORT", "").strip():
        path = Path(env_path)
        if path.is_file():
            return path

    parent = repo_root().parent
    candidates = [
        parent
        / "scientific-memory"
        / "corpus"
        / "pcs"
        / "claims"
        / claim_id
        / "scientific_memory_import_report.json",
        workdir / "scientific_memory_import_report.json",
    ]
    for path in candidates:
        if path.is_file():
            return path

    raise FileNotFoundError(
        "scientific_memory_import_report.json not found. Import the signed bundle "
        "with Scientific Memory (just pcs-import-bundle) or set SCIENTIFIC_MEMORY_IMPORT_REPORT."
    )


def normalize_import_report(report: dict[str, Any]) -> dict[str, Any]:
    """Make SM import report stable for committed release fixtures."""
    normalized = dict(report)
    normalized["source_bundle_path"] = "signed_science_claim_bundle.json"
    imported_at = normalized.get("imported_at")
    if isinstance(imported_at, str) and imported_at:
        # Drop sub-second noise for reproducible manifests across regenerations.
        if "." in imported_at:
            base, _, tz = imported_at.partition(".")
            if tz.endswith("+00:00"):
                normalized["imported_at"] = f"{base}Z"
            elif "+" in tz or tz.endswith("Z"):
                normalized["imported_at"] = base + (tz if tz.startswith("+") else "Z")
    return normalized


def import_chain_artifacts(
    workdir: Path,
    *,
    release_candidate: str = "pcs-v0.1.0-rc1",
    commits: dict[str, str] | None = None,
    claim_id: str = DEFAULT_CLAIM_ID,
) -> Path:
    """Copy real cross-repo chain outputs into examples/labtrust-release/."""
    if not _chain_artifacts_present(workdir):
        missing = [name for name in CHAIN_ARTIFACTS if not (workdir / name).is_file()]
        raise FileNotFoundError(
            f"chain workdir {workdir} is missing artifacts: {', '.join(missing)}",
        )

    out = release_dir()
    out.mkdir(parents=True, exist_ok=True)

    for name in CHAIN_ARTIFACTS:
        shutil.copy2(workdir / name, out / name)

    sm_report_path = resolve_sm_import_report(workdir, claim_id=claim_id)
    sm_report = normalize_import_report(
        json.loads(sm_report_path.read_text(encoding="utf-8")),
    )
    write_json(out / "scientific_memory_import_report.json", sm_report)

    pin_commits = commits or resolve_five_repo_commits()
    for key in COMMIT_KEYS:
        commit = pin_commits.get(key, "")
        if not isinstance(commit, str) or len(commit) != 40:
            raise ValueError(f"invalid {key}: {commit!r}")
        if is_placeholder_commit(commit):
            raise ValueError(f"{key} is a placeholder commit; set {key.upper()} env or rebuild siblings")

    artifacts = {name: file_digest((out / name).read_bytes()) for name in MANIFEST_ARTIFACTS}

    manifest: dict[str, Any] = {
        "schema_version": "v0",
        "release_candidate": release_candidate,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        **pin_commits,
        "artifacts": artifacts,
    }
    write_json(out / MANIFEST_NAME, manifest)
    return out


def write_release_fixtures(
    *,
    workdir: Path | None = None,
    release_candidate: str = "pcs-v0.1.0-rc1",
) -> Path:
    work = workdir or resolve_chain_workdir()
    path = import_chain_artifacts(work, release_candidate=release_candidate)
    drift = validate_release_manifest(path / MANIFEST_NAME)
    if drift:
        raise RuntimeError("release fixtures failed self-check:\n" + "\n".join(drift))
    return path


def validate_release_manifest(manifest_path: Path) -> list[str]:
    errors: list[str] = []
    if not manifest_path.is_file():
        return [f"missing manifest: {manifest_path}"]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"manifest JSON parse error: {exc}"]

    if not isinstance(manifest, dict):
        return ["manifest root must be a JSON object"]

    base = manifest_path.parent

    for key in COMMIT_KEYS:
        commit = manifest.get(key)
        if not isinstance(commit, str) or len(commit) != 40:
            errors.append(f"manifest missing or invalid {key}")
            continue
        if is_placeholder_commit(commit):
            errors.append(f"{key} uses placeholder provenance: {commit}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("manifest artifacts must be an object")
        return errors

    if set(artifacts) != set(MANIFEST_ARTIFACTS):
        missing = set(MANIFEST_ARTIFACTS) - set(artifacts)
        extra = set(artifacts) - set(MANIFEST_ARTIFACTS)
        if missing:
            errors.append(f"manifest artifacts missing keys: {sorted(missing)}")
        if extra:
            errors.append(f"manifest artifacts has unexpected keys: {sorted(extra)}")

    for name in MANIFEST_ARTIFACTS:
        path = base / name
        if not path.is_file():
            errors.append(f"missing manifest artifact file {name}")
            continue
        expected = artifacts.get(name)
        actual = file_digest(path.read_bytes())
        if expected != actual:
            errors.append(f"{name}: manifest digest mismatch (expected {expected}, got {actual})")

    for name in RELEASE_PCS_ARTIFACTS:
        path = base / name
        if not path.is_file():
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"{name}: pcs validate failed: {exc}")
        except Exception as exc:
            errors.append(f"{name}: validation failed: {exc}")

    signed_path = base / "signed_science_claim_bundle.json"
    if signed_path.is_file():
        try:
            signed = json.loads(signed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"signed_science_claim_bundle.json: JSON parse error: {exc}")
        else:
            vr = signed.get("verification_result")
            if not isinstance(vr, dict):
                errors.append("signed_science_claim_bundle.json: missing verification_result object")
            elif vr.get("status") != "ProofChecked":
                errors.append(
                    "signed_science_claim_bundle.json: "
                    f"verification_result.status must be ProofChecked (got {vr.get('status')!r})",
                )

    verification_path = base / "verification_result.json"
    if verification_path.is_file():
        try:
            vr_file = json.loads(verification_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"verification_result.json: JSON parse error: {exc}")
        else:
            if not isinstance(vr_file, dict):
                errors.append("verification_result.json: root must be a JSON object")
            elif vr_file.get("status") != "ProofChecked":
                errors.append(
                    "verification_result.json: status must be ProofChecked "
                    f"(got {vr_file.get('status')!r})",
                )

    return errors


def verify_release_fixtures() -> list[str]:
    return validate_release_manifest(release_dir() / MANIFEST_NAME)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PCS LabTrust release fixtures")
    parser.add_argument("--write", action="store_true", help="Import chain outputs into release fixtures")
    parser.add_argument("--verify", action="store_true", help="Verify release fixtures")
    parser.add_argument(
        "--workdir",
        type=Path,
        help="Chain workdir (default: PCS_CHAIN_WORK or ../LabTrust-Gym)",
    )
    parser.add_argument(
        "--release-candidate",
        default="pcs-v0.1.0-rc1",
        help="Release candidate id recorded in manifest",
    )
    args = parser.parse_args(argv)

    if args.write:
        path = write_release_fixtures(
            workdir=args.workdir,
            release_candidate=args.release_candidate,
        )
        print(f"Wrote release fixtures under {path}")
        return 0
    if args.verify:
        drift = verify_release_fixtures()
        if drift:
            for err in drift:
                print(f"FAIL {err}", file=sys.stderr)
            return 1
        print("OK labtrust-release fixtures")
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
