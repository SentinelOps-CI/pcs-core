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

from pcs_core.hash import SIGNATURE_FIELD, canonical_hash
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


def conformance_dir() -> Path:
    return examples_dir() / CONFORMANCE_DIR_NAME


def file_digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def write_json(path: Path, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def is_placeholder_commit(commit: str) -> bool:
    return bool(PLACEHOLDER_COMMIT_RE.fullmatch(commit.strip()))


def manifest_commit_key(source_repo: str) -> str | None:
    repo = source_repo.lower()
    for needle, key in REPO_COMMIT_KEYS:
        if needle in repo:
            return key
    return None


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
    imported_at = normalized.get("imported_at")
    if isinstance(imported_at, str) and imported_at and "." in imported_at:
        base, _, tz = imported_at.partition(".")
        if tz.endswith("+00:00"):
            normalized["imported_at"] = f"{base}Z"
        elif "+" in tz or tz.endswith("Z"):
            normalized["imported_at"] = base + (tz if tz.startswith("+") else "Z")
    return normalized


def _resign(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out.pop(SIGNATURE_FIELD, None)
    out[SIGNATURE_FIELD] = canonical_hash(out)
    return out


def _set_provenance(obj: dict[str, Any], *, repo: str, commit: str) -> None:
    obj["source_repo"] = repo
    obj["source_commit"] = commit
    obj.pop("local_dev", None)


def align_release_provenance(out: Path, commits: dict[str, str]) -> None:
    """Rewrite embedded source_commit fields and re-sign PCS artifacts."""
    lt = commits["labtrust_gym_commit"]
    ce = commits["certifyedge_commit"]
    pf = commits["provability_fabric_commit"]

    receipt_path = out / "runtime_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    _set_provenance(receipt, repo=LABTRUST_SOURCE_REPO, commit=lt)
    write_json(receipt_path, _resign(receipt))

    cert_path = out / "trace_certificate.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    _set_provenance(cert, repo=CERTIFYEDGE_SOURCE_REPO, commit=ce)
    write_json(cert_path, _resign(cert))

    for name in ("science_claim_bundle.pending.json", "science_claim_bundle.certified.json"):
        bundle = json.loads((out / name).read_text(encoding="utf-8"))
        _align_science_claim_bundle(bundle, lt=lt, ce=ce)
        write_json(out / name, _resign(bundle))

    vr_path = out / "verification_result.json"
    vr = json.loads(vr_path.read_text(encoding="utf-8"))
    _set_provenance(vr, repo=PF_SOURCE_REPO, commit=pf)
    write_json(vr_path, _resign(vr))

    signed_path = out / "signed_science_claim_bundle.json"
    signed = json.loads(signed_path.read_text(encoding="utf-8"))
    scb = signed.get("science_claim_bundle")
    if isinstance(scb, dict):
        _align_science_claim_bundle(scb, lt=lt, ce=ce)
    embedded_vr = signed.get("verification_result")
    if isinstance(embedded_vr, dict):
        _set_provenance(embedded_vr, repo=PF_SOURCE_REPO, commit=pf)
        signed["verification_result"] = _resign(embedded_vr)
    _set_provenance(signed, repo=PF_SOURCE_REPO, commit=pf)
    write_json(signed_path, _resign(signed))


def _align_science_claim_bundle(bundle: dict[str, Any], *, lt: str, ce: str) -> None:
    _set_provenance(bundle, repo=LABTRUST_SOURCE_REPO, commit=lt)
    for key in ("claim_artifact", "assumption_set", "evidence_bundle"):
        part = bundle.get(key)
        if isinstance(part, dict):
            _set_provenance(part, repo=LABTRUST_SOURCE_REPO, commit=lt)
            bundle[key] = _resign(part)
    receipts = bundle.get("runtime_receipts")
    if isinstance(receipts, list):
        aligned: list[Any] = []
        for item in receipts:
            if isinstance(item, dict):
                _set_provenance(item, repo=LABTRUST_SOURCE_REPO, commit=lt)
                aligned.append(_resign(item))
            else:
                aligned.append(item)
        bundle["runtime_receipts"] = aligned
    certs = bundle.get("certificates")
    if isinstance(certs, list):
        aligned_certs: list[Any] = []
        for item in certs:
            if isinstance(item, dict):
                _set_provenance(item, repo=CERTIFYEDGE_SOURCE_REPO, commit=ce)
                aligned_certs.append(_resign(item))
            else:
                aligned_certs.append(item)
        bundle["certificates"] = aligned_certs


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

    pin_commits = commits or resolve_five_repo_commits()
    for key in COMMIT_KEYS:
        commit = pin_commits.get(key, "")
        if not isinstance(commit, str) or len(commit) != 40:
            raise ValueError(f"invalid {key}: {commit!r}")
        if is_placeholder_commit(commit):
            raise ValueError(f"{key} is a placeholder commit; set {key.upper()} env or rebuild siblings")

    align_release_provenance(out, pin_commits)

    sm_report_path = resolve_sm_import_report(workdir, claim_id=claim_id)
    sm_report = normalize_import_report(
        json.loads(sm_report_path.read_text(encoding="utf-8")),
        commits=pin_commits,
    )
    write_json(out / "scientific_memory_import_report.json", sm_report)

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
            if isinstance(commit, str) and is_placeholder_commit(commit):
                errors.append(
                    f"{label}: placeholder source_commit at {node_path}: {commit}",
                )
            if isinstance(repo, str) and isinstance(commit, str):
                continue
        if isinstance(node, str) and is_placeholder_commit(node):
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
        _scan_forbidden_values(certified, label="science_claim_bundle.certified.json", errors=errors)
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
        scb = bundle_doc if bundle_name.startswith("science") else bundle_doc.get(
            "science_claim_bundle",
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
                errors.append("signed_science_claim_bundle.json: missing verification_result object")
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
