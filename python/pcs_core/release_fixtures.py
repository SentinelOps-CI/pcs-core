"""Generate and verify PCS v0.1 LabTrust release fixture bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pcs_core.hash import canonical_hash
from pcs_core.paths import examples_dir, repo_root
from pcs_core.validate import validate_file

RELEASE_DIR_NAME = "labtrust-release"
MANIFEST_NAME = "RELEASE_FIXTURE_MANIFEST.json"

RELEASE_PCS_ARTIFACTS = (
    "runtime_receipt.json",
    "trace_certificate.json",
    "science_claim_bundle.pending.json",
    "science_claim_bundle.certified.json",
    "verification_result.json",
    "signed_science_claim_bundle.json",
)

MANIFEST_ARTIFACTS = (
    "trace.json",
    *RELEASE_PCS_ARTIFACTS,
    "scientific_memory_import_report.json",
)

DEFAULT_COMMITS = {
    "labtrust_gym_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "certifyedge_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "provability_fabric_commit": "cccccccccccccccccccccccccccccccccccccccc",
    "scientific_memory_commit": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
}


def release_dir() -> Path:
    return examples_dir() / RELEASE_DIR_NAME


def conformance_dir() -> Path:
    return examples_dir() / "labtrust"


def file_digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def write_json(path: Path, data: dict[str, Any]) -> bytes:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return text.encode("utf-8")


def git_commit_or(env_key: str, default: str) -> str:
    value = os.environ.get(env_key, "").strip()
    if value:
        return value
    return default


def current_pcs_core_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root(),
                text=True,
            )
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "0000000000000000000000000000000000000000"


def build_release_artifacts() -> dict[str, dict[str, Any] | list[Any]]:
    """Build a coherent qc-release RC1 artifact graph with consistent hashes."""
    trace: dict[str, Any] = {
        "run_id": "runs/qc-release-rc1",
        "schema_version": "v0",
        "exported_at": "2026-05-16T12:00:00Z",
        "producer": "labtrust-gym",
        "producer_version": "0.1.0",
        "events": [
            {
                "event_id": "evt-1",
                "kind": "simulation_step",
                "timestamp": "2026-05-16T11:59:00Z",
                "payload": {"step": "qc_release_check", "outcome": "pass"},
            }
        ],
    }

    lt_commit = git_commit_or("LABTRUST_GYM_COMMIT", DEFAULT_COMMITS["labtrust_gym_commit"])
    ce_commit = git_commit_or("CERTIFYEDGE_COMMIT", DEFAULT_COMMITS["certifyedge_commit"])
    pf_commit = git_commit_or(
        "PROVABILITY_FABRIC_COMMIT",
        DEFAULT_COMMITS["provability_fabric_commit"],
    )
    sm_commit = git_commit_or(
        "SCIENTIFIC_MEMORY_COMMIT",
        DEFAULT_COMMITS["scientific_memory_commit"],
    )

    trace_bytes = json.dumps(trace, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    trace_hash = file_digest(trace_bytes)

    runtime_receipt: dict[str, Any] = {
        "receipt_id": "receipt-qc-release-rc1-001",
        "schema_version": "v0",
        "run_id": "runs/qc-release-rc1",
        "environment": {"platform": "linux", "labtrust_version": "0.1.0"},
        "started_at": "2026-05-16T11:58:00Z",
        "ended_at": "2026-05-16T12:00:00Z",
        "status": "RuntimeObserved",
        "run_outcome": "passed",
        "final_reason_code": "ok",
        "released": True,
        "events_hash": file_digest(b"events-qc-release-rc1-v0.1"),
        "policy_hash": file_digest(b"policy-qc-release-rc1-v0.1"),
        "trace_hash": trace_hash,
        "producer": "labtrust-gym",
        "producer_version": "0.1.0",
        "source_repo": "https://github.com/fraware/LabTrust-Gym",
        "source_commit": lt_commit,
        "input_hashes": {"spec": file_digest(b"spec-qc-release-rc1-v0.1")},
        "output_hashes": {"trace.json": trace_hash},
    }
    runtime_receipt["signature_or_digest"] = canonical_hash(runtime_receipt)

    trace_certificate: dict[str, Any] = {
        "certificate_id": "cert-trace-qc-release-rc1",
        "schema_version": "v0",
        "trace_hash": trace_hash,
        "spec_hash": runtime_receipt["input_hashes"]["spec"],
        "property_id": "qc_release.temporal.safety",
        "checker": "certifyedge",
        "checker_version": "0.1.0",
        "status": "CertificateChecked",
        "counterexample_ref": None,
        "created_at": "2026-05-16T12:10:00Z",
        "producer": "certifyedge",
        "producer_version": "0.1.0",
        "source_repo": "https://github.com/fraware/CertifyEdge",
        "source_commit": ce_commit,
    }
    trace_certificate["signature_or_digest"] = canonical_hash(trace_certificate)

    pending = json.loads(
        (conformance_dir() / "science_claim_bundle.pending.valid.json").read_text(
            encoding="utf-8",
        ),
    )
    pending["bundle_id"] = "scb-qc-release-rc1-pending"
    pending["runtime_receipts"] = [runtime_receipt]
    pending["source_commit"] = lt_commit
    pending["claim_artifact"]["source_commit"] = lt_commit
    pending["assumption_set"]["source_commit"] = lt_commit
    pending["evidence_bundle"]["source_commit"] = lt_commit
    pending["signature_or_digest"] = canonical_hash(pending)

    certified = json.loads(
        (conformance_dir() / "science_claim_bundle.certified.valid.json").read_text(
            encoding="utf-8",
        ),
    )
    certified["bundle_id"] = "scb-qc-release-rc1"
    certified["runtime_receipts"] = [runtime_receipt]
    certified["certificates"] = [trace_certificate]
    certified["claim_artifact"]["status"] = "CertificateChecked"
    certified["claim_artifact"]["certificate_refs"] = [trace_certificate["certificate_id"]]
    certified["claim_artifact"]["source_commit"] = lt_commit
    certified["assumption_set"]["source_commit"] = lt_commit
    certified["evidence_bundle"]["certificate_refs"] = [trace_certificate["certificate_id"]]
    certified["evidence_bundle"]["source_commit"] = lt_commit
    certified["source_commit"] = lt_commit
    certified["signature_or_digest"] = canonical_hash(certified)

    verification_result: dict[str, Any] = {
        "verification_id": "verify-scb-qc-release-rc1",
        "schema_version": "v0",
        "bundle_id": certified["bundle_id"],
        "verifier": "provability-fabric",
        "verifier_version": "0.1.0",
        "status": "ProofChecked",
        "checks": [
            {
                "check_id": "schema-valid",
                "description": "ScienceClaimBundle conforms to PCS schema",
                "status": "passed",
                "details": {},
            },
            {
                "check_id": "trace-hash-alignment",
                "description": "Runtime receipt trace_hash matches certificate",
                "status": "passed",
                "details": {"trace_hash": trace_hash},
            },
        ],
        "created_at": "2026-05-16T12:20:00Z",
        "source_repo": "https://github.com/SentinelOps-CI/provability-fabric",
        "source_commit": pf_commit,
    }
    verification_result["signature_or_digest"] = canonical_hash(verification_result)

    signed: dict[str, Any] = {
        "schema_version": "v0",
        "signed_bundle_id": "signed-scb-qc-release-rc1",
        "science_claim_bundle": certified,
        "verification_result": verification_result,
        "signer": "provability-fabric",
        "signed_at": "2026-05-16T12:25:00Z",
        "source_repo": "https://github.com/SentinelOps-CI/provability-fabric",
        "source_commit": pf_commit,
    }
    signed["signature_or_digest"] = canonical_hash(signed)

    import_report: dict[str, Any] = {
        "schema_version": "v0",
        "report_id": "sm-import-qc-release-rc1",
        "signed_bundle_id": signed["signed_bundle_id"],
        "import_status": "success",
        "imported_at": "2026-05-16T12:30:00Z",
        "importer": "scientific-memory",
        "importer_version": "0.1.0",
        "source_repo": "https://github.com/fraware/scientific-memory",
        "source_commit": sm_commit,
        "checks": [
            {"check_id": "pcs-validate", "status": "passed"},
            {"check_id": "schema-version-v0", "status": "passed"},
            {"check_id": "import-contract", "status": "passed"},
        ],
        "rendered_guarantee": "certificate_checked",
    }
    import_report["signature_or_digest"] = file_digest(
        json.dumps(import_report, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )

    return {
        "trace": trace,
        "trace_bytes": trace_bytes,
        "runtime_receipt": runtime_receipt,
        "trace_certificate": trace_certificate,
        "pending": pending,
        "certified": certified,
        "verification_result": verification_result,
        "signed": signed,
        "import_report": import_report,
        "commits": {
            "labtrust_gym_commit": lt_commit,
            "certifyedge_commit": ce_commit,
            "provability_fabric_commit": pf_commit,
            "scientific_memory_commit": sm_commit,
        },
    }


def write_release_fixtures(*, release_candidate: str = "pcs-v0.1.0-rc1") -> Path:
    out = release_dir()
    out.mkdir(parents=True, exist_ok=True)

    built = build_release_artifacts()

    (out / "trace.json").write_bytes(built["trace_bytes"])  # type: ignore[arg-type]

    for name, key in [
        ("runtime_receipt.json", "runtime_receipt"),
        ("trace_certificate.json", "trace_certificate"),
        ("science_claim_bundle.pending.json", "pending"),
        ("science_claim_bundle.certified.json", "certified"),
        ("verification_result.json", "verification_result"),
        ("signed_science_claim_bundle.json", "signed"),
    ]:
        write_json(out / name, built[key])  # type: ignore[index]

    write_json(
        out / "scientific_memory_import_report.json",
        built["import_report"],  # type: ignore[index]
    )

    artifacts = {
        name: file_digest((out / name).read_bytes()) for name in MANIFEST_ARTIFACTS
    }
    commits = built["commits"]  # type: ignore[assignment]

    manifest: dict[str, Any] = {
        "schema_version": "v0",
        "release_candidate": release_candidate,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "pcs_core_commit": current_pcs_core_commit(),
        "labtrust_gym_commit": commits["labtrust_gym_commit"],
        "certifyedge_commit": commits["certifyedge_commit"],
        "provability_fabric_commit": commits["provability_fabric_commit"],
        "scientific_memory_commit": commits["scientific_memory_commit"],
        "artifacts": artifacts,
    }
    write_json(out / MANIFEST_NAME, manifest)
    return out


def verify_release_fixtures() -> list[str]:
    errors: list[str] = []
    out = release_dir()
    manifest_path = out / MANIFEST_NAME
    if not manifest_path.is_file():
        return [f"missing {manifest_path}"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in RELEASE_PCS_ARTIFACTS:
        path = out / name
        if not path.is_file():
            errors.append(f"missing release artifact {name}")
            continue
        try:
            validate_file(path)
        except Exception as exc:
            errors.append(f"{name}: validation failed: {exc}")

    for commit_key in (
        "pcs_core_commit",
        "labtrust_gym_commit",
        "certifyedge_commit",
        "provability_fabric_commit",
        "scientific_memory_commit",
    ):
        commit = manifest.get(commit_key)
        if not isinstance(commit, str) or len(commit) < 7:
            errors.append(f"manifest missing {commit_key}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("manifest artifacts must be an object")
        return errors

    for name in MANIFEST_ARTIFACTS:
        path = out / name
        if not path.is_file():
            errors.append(f"missing manifest artifact file {name}")
            continue
        expected = artifacts.get(name)
        actual = file_digest(path.read_bytes())
        if expected != actual:
            errors.append(f"{name}: manifest digest mismatch (expected {expected}, got {actual})")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PCS LabTrust release fixtures")
    parser.add_argument("--write", action="store_true", help="Generate release fixtures")
    parser.add_argument("--verify", action="store_true", help="Verify release fixtures")
    parser.add_argument(
        "--release-candidate",
        default="pcs-v0.1.0-rc1",
        help="Release candidate id recorded in manifest",
    )
    args = parser.parse_args(argv)

    if args.write:
        path = write_release_fixtures(release_candidate=args.release_candidate)
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
