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
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pcs_core.paths import examples_dir, repo_root
from pcs_core.validate import ValidationError, validate_file

RELEASE_DIR_NAME = "labtrust-release"
RELEASE_RUN_DIR_NAME = "release-run"
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

REPO_COMMIT_KEYS: tuple[tuple[str, str], ...] = (
    ("labtrust", "labtrust_gym_commit"),
    ("labtrust-gym", "labtrust_gym_commit"),
    ("certifyedge", "certifyedge_commit"),
    ("provability-fabric", "provability_fabric_commit"),
    ("provability_fabric", "provability_fabric_commit"),
    ("scientific-memory", "scientific_memory_commit"),
    ("scientific_memory", "scientific_memory_commit"),
    ("pcs-core", "pcs_core_commit"),
    ("pcs_core", "pcs_core_commit"),
)

DEFAULT_CLAIM_ID = "claim-pcs-qc-release-v0.1"

LABTRUST_SOURCE_REPO = "https://github.com/fraware/LabTrust-Gym"
CERTIFYEDGE_SOURCE_REPO = "https://github.com/fraware/CertifyEdge"
PF_SOURCE_REPO = "https://github.com/SentinelOps-CI/provability-fabric"
SM_SOURCE_REPO = "https://github.com/fraware/scientific-memory"


def release_dir() -> Path:
    return examples_dir() / RELEASE_DIR_NAME


def release_run_dir() -> Path:
    return repo_root() / RELEASE_RUN_DIR_NAME


def conformance_dir() -> Path:
    return examples_dir() / CONFORMANCE_DIR_NAME


def file_digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def sync_legacy_manifest_artifact_hashes(directory: Path | None = None) -> dict[str, str]:
    """Align RELEASE_FIXTURE_MANIFEST.json artifact digests with on-disk bytes."""
    base = directory or release_dir()
    manifest_path = base / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError(f"{manifest_path}: missing artifacts object")
    updated: dict[str, str] = {}
    for name in MANIFEST_ARTIFACTS:
        path = base / name
        digest = file_digest(path.read_bytes())
        artifacts[str(name)] = digest
        updated[str(name)] = digest
    manifest["artifacts"] = artifacts
    write_json(manifest_path, manifest)
    return updated


def write_json(path: Path, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def is_placeholder_commit(commit: str) -> bool:
    return bool(PLACEHOLDER_COMMIT_RE.fullmatch(commit.strip()))


RELEASE_PATTERN_PLACEHOLDER_RE = re.compile(r"^(?:a{40}|b{40}|c{40}|d{40}|e{40})$")


def is_release_pattern_placeholder(commit: str) -> bool:
    return bool(RELEASE_PATTERN_PLACEHOLDER_RE.fullmatch(commit.strip()))


def is_zero_commit(commit: str) -> bool:
    return commit.strip() == "0" * 40


def manifest_commit_key(source_repo: str) -> str | None:
    repo = source_repo.lower()
    for needle, key in REPO_COMMIT_KEYS:
        if needle in repo:
            return key
    return None


def git_commit_at(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=path,
            text=True,
        ).strip()
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


def normalize_import_report(
    report: dict[str, Any],
    *,
    commits: dict[str, str],
) -> dict[str, Any]:
    """Make SM import report stable and provenance-consistent for release fixtures."""
    normalized = dict(report)
    normalized["source_bundle_path"] = "signed_science_claim_bundle.json"
    normalized["source_repo"] = SM_SOURCE_REPO
    normalized["source_commit"] = commits["scientific_memory_commit"]
    normalized["scientific_memory_commit"] = commits["scientific_memory_commit"]
    imported_at = normalized.get("imported_at")
    if isinstance(imported_at, str) and imported_at and "." in imported_at:
        base, _, tz = imported_at.partition(".")
        if tz.endswith("+00:00"):
            normalized["imported_at"] = f"{base}Z"
        elif "+" in tz or tz.endswith("Z"):
            normalized["imported_at"] = base + (tz if tz.startswith("+") else "Z")
    return normalized


def _top_level_commit_for_repo(doc: dict[str, Any], repo_url: str) -> str | None:
    if doc.get("source_repo") == repo_url:
        commit = doc.get("source_commit")
        return commit if isinstance(commit, str) else None
    return None


def commits_from_release_run(run_dir: Path) -> dict[str, str]:
    """Derive manifest commit pins from a single atomic release-run."""
    receipt = _load_json(run_dir / "runtime_receipt.json")
    cert = _load_json(run_dir / "trace_certificate.json")
    vr = _load_json(run_dir / "verification_result.json")
    sm = _load_json(run_dir / "scientific_memory_import_report.json")
    if not receipt or not cert or not vr or not sm:
        raise ValueError("release-run is missing artifacts required to derive manifest commits")

    parent = repo_root().parent
    pf_commit = _top_level_commit_for_repo(vr, PF_SOURCE_REPO) or git_commit_or(
        "PROVABILITY_FABRIC_COMMIT",
        parent / "provability-fabric",
    )

    return {
        "pcs_core_commit": git_commit_at(repo_root()),
        "labtrust_gym_commit": str(receipt["source_commit"]),
        "certifyedge_commit": str(cert["source_commit"]),
        "provability_fabric_commit": pf_commit,
        "scientific_memory_commit": str(sm["source_commit"]),
    }


def build_release_run(
    workdir: Path,
    *,
    release_candidate: str = "pcs-v0.1.0-rc1",
    claim_id: str = DEFAULT_CLAIM_ID,
    run_dir: Path | None = None,
) -> Path:
    """Populate release-run/ from one cross-repo chain workdir (no partial updates)."""
    if not _chain_artifacts_present(workdir):
        missing = [name for name in CHAIN_ARTIFACTS if not (workdir / name).is_file()]
        raise FileNotFoundError(
            f"chain workdir {workdir} is missing artifacts: {', '.join(missing)}",
        )

    out = run_dir or release_run_dir()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for name in CHAIN_ARTIFACTS:
        shutil.copy2(workdir / name, out / name)

    receipt = _load_json(out / "runtime_receipt.json")
    cert = _load_json(out / "trace_certificate.json")
    vr = _load_json(out / "verification_result.json")
    if not receipt or not cert or not vr:
        raise ValueError("release-run missing receipt, certificate, or verification_result")

    parent = repo_root().parent
    pin_commits = {
        "pcs_core_commit": git_commit_at(repo_root()),
        "labtrust_gym_commit": str(receipt["source_commit"]),
        "certifyedge_commit": str(cert["source_commit"]),
        "provability_fabric_commit": git_commit_or(
            "PROVABILITY_FABRIC_COMMIT",
            parent / "provability-fabric",
        ),
        "scientific_memory_commit": git_commit_or(
            "SCIENTIFIC_MEMORY_COMMIT",
            parent / "scientific-memory",
        ),
    }

    sm_report_path = resolve_sm_import_report(workdir, claim_id=claim_id)
    sm_report = normalize_import_report(
        json.loads(sm_report_path.read_text(encoding="utf-8")),
        commits=pin_commits,
    )
    write_json(out / "scientific_memory_import_report.json", sm_report)
    pin_commits = commits_from_release_run(out)

    for key in COMMIT_KEYS:
        commit = pin_commits[key]
        if is_placeholder_commit(commit):
            raise ValueError(f"{key} is a placeholder commit: {commit}")

    artifacts = {name: file_digest((out / name).read_bytes()) for name in MANIFEST_ARTIFACTS}
    manifest: dict[str, Any] = {
        "schema_version": "v0",
        "release_candidate": release_candidate,
        "generated_at": datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        ),
        **pin_commits,
        "artifacts": artifacts,
    }
    write_json(out / MANIFEST_NAME, manifest)
    return out


def promote_release_run(run_dir: Path, *, target: Path | None = None) -> Path:
    """Atomically replace examples/labtrust-release/ with a validated release-run/."""
    from pcs_core.release_chain import validate_release_chain

    target_dir = target or release_dir()
    issues = validate_release_chain(run_dir)
    if issues:
        lines = "\n".join(issue.format() for issue in issues)
        raise RuntimeError(f"release-run failed chain validation:\n{lines}")

    preserved: list[tuple[Path, bytes]] = []
    if target_dir.exists():
        for pattern in ("invalid_*.json", "README.md"):
            for path in target_dir.glob(pattern):
                preserved.append((path, path.read_bytes()))

    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(run_dir, target_dir)

    for path, content in preserved:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    from pcs_core.protocol_fixtures import write_labtrust_protocol_artifacts

    write_labtrust_protocol_artifacts(target_dir)
    return target_dir


def write_release_fixtures(
    *,
    workdir: Path | None = None,
    release_candidate: str = "pcs-v0.1.0-rc1",
) -> Path:
    work = workdir or resolve_chain_workdir()
    run_path = build_release_run(work, release_candidate=release_candidate)
    return promote_release_run(run_path)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _iter_nodes(obj: Any, *, path: str = "$") -> Iterator[tuple[str, Any]]:
    yield path, obj
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}"
            yield from _iter_nodes(value, path=child)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            yield from _iter_nodes(item, path=f"{path}[{index}]")


def _scan_forbidden_values(obj: Any, *, label: str, errors: list[str]) -> None:
    for node_path, node in _iter_nodes(obj):
        if isinstance(node, dict):
            if node.get("local_dev") is True:
                errors.append(f"{label}: local_dev=true at {node_path}")
            repo = node.get("source_repo")
            commit = node.get("source_commit")
            if isinstance(commit, str) and commit == "0" * 40:
                errors.append(
                    f"{label}: zero source_commit at {node_path}: {commit}",
                )
            elif isinstance(commit, str) and is_placeholder_commit(commit):
                errors.append(
                    f"{label}: placeholder source_commit at {node_path}: {commit}",
                )
            if isinstance(repo, str) and isinstance(commit, str):
                continue
        if isinstance(node, str) and node == "0" * 40:
            errors.append(f"{label}: zero commit string at {node_path}: {node}")
        elif isinstance(node, str) and is_placeholder_commit(node):
            errors.append(f"{label}: placeholder commit string at {node_path}: {node}")


def _expect_provenance(
    obj: dict[str, Any],
    *,
    label: str,
    expected_repo: str,
    expected_commit: str,
    errors: list[str],
) -> None:
    repo = obj.get("source_repo")
    commit = obj.get("source_commit")
    if repo != expected_repo:
        errors.append(f"{label}: source_repo expected {expected_repo!r}, got {repo!r}")
    if commit != expected_commit:
        errors.append(
            f"{label}: source_commit expected {expected_commit}, got {commit!r}",
        )


def _validate_nested_provenance(
    base: Path,
    manifest: dict[str, Any],
    errors: list[str],
) -> None:
    commits = {key: manifest[key] for key in COMMIT_KEYS}
    lt = commits["labtrust_gym_commit"]
    ce = commits["certifyedge_commit"]
    pf = commits["provability_fabric_commit"]
    sm = commits["scientific_memory_commit"]

    certified_path = base / "science_claim_bundle.certified.json"
    certified = _load_json(certified_path)
    if certified is None:
        errors.append("science_claim_bundle.certified.json: invalid JSON")
    else:
        _scan_forbidden_values(
            certified, label="science_claim_bundle.certified.json", errors=errors
        )
        for key in ("claim_artifact", "assumption_set", "evidence_bundle"):
            part = certified.get(key)
            if isinstance(part, dict):
                _expect_provenance(
                    part,
                    label=f"certified.{key}",
                    expected_repo=LABTRUST_SOURCE_REPO,
                    expected_commit=lt,
                    errors=errors,
                )
        receipts = certified.get("runtime_receipts")
        if isinstance(receipts, list):
            for i, receipt in enumerate(receipts):
                if isinstance(receipt, dict):
                    _expect_provenance(
                        receipt,
                        label=f"certified.runtime_receipts[{i}]",
                        expected_repo=LABTRUST_SOURCE_REPO,
                        expected_commit=lt,
                        errors=errors,
                    )
        _expect_provenance(
            certified,
            label="certified.bundle",
            expected_repo=LABTRUST_SOURCE_REPO,
            expected_commit=lt,
            errors=errors,
        )
        certs = certified.get("certificates")
        if isinstance(certs, list):
            for i, cert in enumerate(certs):
                if isinstance(cert, dict):
                    _expect_provenance(
                        cert,
                        label=f"certified.certificates[{i}]",
                        expected_repo=CERTIFYEDGE_SOURCE_REPO,
                        expected_commit=ce,
                        errors=errors,
                    )

    signed_path = base / "signed_science_claim_bundle.json"
    signed = _load_json(signed_path)
    if signed is None:
        errors.append("signed_science_claim_bundle.json: invalid JSON")
    else:
        _scan_forbidden_values(signed, label="signed_science_claim_bundle.json", errors=errors)
        scb = signed.get("science_claim_bundle")
        if isinstance(scb, dict):
            for key in ("claim_artifact", "assumption_set", "evidence_bundle"):
                part = scb.get(key)
                if isinstance(part, dict):
                    _expect_provenance(
                        part,
                        label=f"signed.science_claim_bundle.{key}",
                        expected_repo=LABTRUST_SOURCE_REPO,
                        expected_commit=lt,
                        errors=errors,
                    )
            receipts = scb.get("runtime_receipts")
            if isinstance(receipts, list):
                for i, receipt in enumerate(receipts):
                    if isinstance(receipt, dict):
                        _expect_provenance(
                            receipt,
                            label=f"signed.science_claim_bundle.runtime_receipts[{i}]",
                            expected_repo=LABTRUST_SOURCE_REPO,
                            expected_commit=lt,
                            errors=errors,
                        )
            _expect_provenance(
                scb,
                label="signed.science_claim_bundle",
                expected_repo=LABTRUST_SOURCE_REPO,
                expected_commit=lt,
                errors=errors,
            )
            certs = scb.get("certificates")
            if isinstance(certs, list):
                for i, cert in enumerate(certs):
                    if isinstance(cert, dict):
                        _expect_provenance(
                            cert,
                            label=f"signed.science_claim_bundle.certificates[{i}]",
                            expected_repo=CERTIFYEDGE_SOURCE_REPO,
                            expected_commit=ce,
                            errors=errors,
                        )
        embedded_vr = signed.get("verification_result")
        if isinstance(embedded_vr, dict):
            _expect_provenance(
                embedded_vr,
                label="signed.verification_result",
                expected_repo=PF_SOURCE_REPO,
                expected_commit=pf,
                errors=errors,
            )
        _expect_provenance(
            signed,
            label="signed.wrapper",
            expected_repo=PF_SOURCE_REPO,
            expected_commit=pf,
            errors=errors,
        )

    receipt = _load_json(base / "runtime_receipt.json")
    if receipt is not None:
        _scan_forbidden_values(receipt, label="runtime_receipt.json", errors=errors)
        _expect_provenance(
            receipt,
            label="runtime_receipt",
            expected_repo=LABTRUST_SOURCE_REPO,
            expected_commit=lt,
            errors=errors,
        )

    cert = _load_json(base / "trace_certificate.json")
    if cert is not None:
        _scan_forbidden_values(cert, label="trace_certificate.json", errors=errors)
        _expect_provenance(
            cert,
            label="trace_certificate",
            expected_repo=CERTIFYEDGE_SOURCE_REPO,
            expected_commit=ce,
            errors=errors,
        )
        if cert.get("status") != "CertificateChecked":
            errors.append(
                f"trace_certificate.status must be CertificateChecked (got {cert.get('status')!r})",
            )

    vr = _load_json(base / "verification_result.json")
    if vr is not None:
        _scan_forbidden_values(vr, label="verification_result.json", errors=errors)
        _expect_provenance(
            vr,
            label="verification_result",
            expected_repo=PF_SOURCE_REPO,
            expected_commit=pf,
            errors=errors,
        )

    sm_report = _load_json(base / "scientific_memory_import_report.json")
    if sm_report is not None:
        _scan_forbidden_values(
            sm_report,
            label="scientific_memory_import_report.json",
            errors=errors,
        )
        if "source_commit" in sm_report:
            _expect_provenance(
                sm_report,
                label="scientific_memory_import_report",
                expected_repo=SM_SOURCE_REPO,
                expected_commit=sm,
                errors=errors,
            )


def _validate_trace_hash_alignment(base: Path, errors: list[str]) -> None:
    trace = _load_json(base / "trace.json")
    receipt = _load_json(base / "runtime_receipt.json")
    cert = _load_json(base / "trace_certificate.json")
    if not trace or not receipt or not cert:
        return
    trace_hash = trace.get("trace_hash")
    receipt_hash = receipt.get("trace_hash")
    cert_hash = cert.get("trace_hash")
    if trace_hash != receipt_hash:
        errors.append(
            f"trace_hash mismatch: trace.json {trace_hash} != runtime_receipt.json {receipt_hash}",
        )
    if trace_hash != cert_hash:
        errors.append(
            f"trace_hash mismatch: trace.json {trace_hash} != trace_certificate.json {cert_hash}",
        )
    for bundle_name in (
        "science_claim_bundle.certified.json",
        "signed_science_claim_bundle.json",
    ):
        bundle_doc = _load_json(base / bundle_name)
        if not bundle_doc:
            continue
        scb = (
            bundle_doc
            if bundle_name.startswith("science")
            else bundle_doc.get(
                "science_claim_bundle",
            )
        )
        if not isinstance(scb, dict):
            continue
        certs = scb.get("certificates")
        if isinstance(certs, list):
            for i, item in enumerate(certs):
                if isinstance(item, dict) and item.get("trace_hash") != trace_hash:
                    errors.append(
                        f"{bundle_name} certificates[{i}].trace_hash != trace trace_hash",
                    )
        receipts = scb.get("runtime_receipts")
        if isinstance(receipts, list):
            for i, item in enumerate(receipts):
                if isinstance(item, dict) and item.get("trace_hash") != trace_hash:
                    errors.append(
                        f"{bundle_name} runtime_receipts[{i}].trace_hash != trace trace_hash",
                    )
    vr = _load_json(base / "verification_result.json")
    if vr and trace_hash:
        verified = vr.get("verified_input")
        if isinstance(verified, dict) and verified.get("trace_hash") != trace_hash:
            errors.append(
                "verification_result.verified_input.trace_hash != canonical trace trace_hash",
            )
    signed = _load_json(base / "signed_science_claim_bundle.json")
    if signed and trace_hash:
        embedded_vr = signed.get("verification_result")
        if isinstance(embedded_vr, dict):
            verified = embedded_vr.get("verified_input")
            if isinstance(verified, dict) and verified.get("trace_hash") != trace_hash:
                errors.append(
                    "signed.verification_result.verified_input.trace_hash "
                    "!= canonical trace trace_hash",
                )


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

    for name in MANIFEST_ARTIFACTS:
        path = base / name
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{name}: JSON parse error: {exc}")
            continue
        _scan_forbidden_values(doc, label=name, errors=errors)
        if isinstance(doc, dict):
            repo = doc.get("source_repo")
            commit = doc.get("source_commit")
            if isinstance(repo, str) and isinstance(commit, str):
                key = manifest_commit_key(repo)
                if key and manifest.get(key) != commit:
                    errors.append(
                        f"{name}: source_commit {commit} does not match manifest {key} "
                        f"({manifest.get(key)})",
                    )

    signed_path = base / "signed_science_claim_bundle.json"
    if signed_path.is_file():
        signed = _load_json(signed_path)
        if signed is None:
            errors.append("signed_science_claim_bundle.json: invalid JSON")
        else:
            vr = signed.get("verification_result")
            if not isinstance(vr, dict):
                errors.append(
                    "signed_science_claim_bundle.json: missing verification_result object"
                )
            elif vr.get("status") != "ProofChecked":
                errors.append(
                    "signed_science_claim_bundle.json: "
                    f"verification_result.status must be ProofChecked (got {vr.get('status')!r})",
                )

    verification_path = base / "verification_result.json"
    if verification_path.is_file():
        vr_file = _load_json(verification_path)
        if vr_file is None:
            errors.append("verification_result.json: invalid JSON")
        elif vr_file.get("status") != "ProofChecked":
            errors.append(
                "verification_result.json: status must be ProofChecked "
                f"(got {vr_file.get('status')!r})",
            )

    _validate_trace_hash_alignment(base, errors)
    _validate_nested_provenance(base, manifest, errors)

    return errors


def verify_release_fixtures() -> list[str]:
    from pcs_core.release_chain import validate_release_chain_messages

    return validate_release_chain_messages(release_dir())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PCS LabTrust release fixtures")
    parser.add_argument(
        "--write", action="store_true", help="Import chain outputs into release fixtures"
    )
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
