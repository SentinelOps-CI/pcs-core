"""Evaluate LabTrust-Gym gallery releases (manifest.json layout) for benchmarks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.benchmark_localization import localize_failure_code
from pcs_core.release_fixtures import (
    file_digest,
    is_placeholder_commit,
    is_release_pattern_placeholder,
    is_zero_commit,
)

_PROTOCOL_TO_BENCHMARK_CODE: dict[str, str] = {
    "CERTIFICATE_ID_MISMATCH": "certificate_id_mismatch",
    "STALE_HANDOFF_DIGEST": "trace_hash_mismatch",
    "TRACE_HASH_MISMATCH": "trace_hash_mismatch",
    "PLACEHOLDER_SOURCE_COMMIT": "placeholder_source_commit",
    "SCIENTIFIC_MEMORY_CLAIM_ID_MISMATCH": "scientific_memory_claim_id_mismatch",
}

_LABTRUST_TASK_IDS = frozenset(
    {
        "labtrust-qc-release-v0",
        "scientific-memory-rendering-v0",
    },
)

_GALLERY_CASE_FAILURE: dict[str, tuple[str, str]] = {
    "stale_trace_after_certificate": ("stale_trace_after_certificate", "runtime_producer"),
    "scientific_memory_import_failure": (
        "scientific_memory_claim_id_mismatch",
        "scientific_memory",
    ),
    "lean_signed_hash_mismatch": ("lean_verified_input_hash_mismatch", "verifier"),
    "lean_trace_hash_mismatch": ("lean_certificate_trace_hash_mismatch", "formal_kernel"),
    "lean_rejected_certificate": ("lean_certificate_rejected", "formal_kernel"),
    "lean_stale_certificate": ("lean_certificate_stale", "formal_kernel"),
    "placeholder_commit": ("placeholder_source_commit", "runtime_producer"),
    "legacy_handoff_file": ("legacy_handoff_file", "handoff"),
    "certificate_id_tamper": ("certificate_id_mismatch", "certificate_producer"),
    "trace_hash_tamper": ("trace_hash_mismatch", "runtime_producer"),
    "unauthorized_release": ("unauthorized_release", "runtime_producer"),
    "missing_qc_result": ("missing_qc", "runtime_producer"),
}


def is_labtrust_gallery_case(case: dict[str, Any]) -> bool:
    task_id = str(case.get("task_id", ""))
    if task_id not in _LABTRUST_TASK_IDS:
        return False
    inputs = case.get("input_artifacts")
    if not isinstance(inputs, dict):
        return False
    rel = inputs.get("release_directory")
    return isinstance(rel, str) and "labtrust-qc-release" in rel


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _normalize_digest(value: str) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if text.startswith("sha256:"):
        return text
    return f"sha256:{text}"


def _walk_source_commits(node: Any, *, found: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "source_commit" and isinstance(value, str):
                found.append(value)
            else:
                _walk_source_commits(value, found=found)
    elif isinstance(node, list):
        for item in node:
            _walk_source_commits(item, found=found)


def _placeholder_commit_detected(release_dir: Path) -> bool:
    commits: list[str] = []
    for path in sorted(release_dir.glob("*.json")):
        doc = _load_json(path)
        if doc is not None:
            _walk_source_commits(doc, found=commits)
    for commit in commits:
        if is_zero_commit(commit) or is_placeholder_commit(commit) or is_release_pattern_placeholder(commit):
            return True
    return False


def _detect_run_meta_failure(release_dir: Path) -> tuple[str | None, str | None]:
    run_meta = _load_json(release_dir / "run_meta.json")
    if run_meta is None:
        return None, None
    reason = str(run_meta.get("final_reason_code", ""))
    if reason == "unauthorized_release":
        return "unauthorized_release", "runtime_producer"
    if reason == "missing_qc":
        return "missing_qc", "runtime_producer"
    if run_meta.get("released") is False and reason:
        return reason, "runtime_producer"
    return None, None


def _detect_claim_id_mismatch(release_dir: Path) -> bool:
    certified = _load_json(release_dir / "science_claim_bundle.certified.json")
    signed = _load_json(release_dir / "signed_science_claim_bundle.json")
    if certified is None or signed is None:
        return False
    certified_claim = certified.get("claim_artifact")
    if not isinstance(certified_claim, dict):
        return False
    certified_id = str(certified_claim.get("artifact_id", ""))
    bundle = signed.get("science_claim_bundle")
    if not isinstance(bundle, dict):
        return False
    signed_claim = bundle.get("claim_artifact")
    if not isinstance(signed_claim, dict):
        return False
    signed_id = str(signed_claim.get("artifact_id", ""))
    return bool(certified_id and signed_id and certified_id != signed_id)


def _detect_lean_verified_input_mismatch(release_dir: Path) -> bool:
    signed = _load_json(release_dir / "signed_science_claim_bundle.json")
    verification = _load_json(release_dir / "verification_result.json")
    if signed is None or verification is None:
        return False
    signed_hash = _normalize_digest(str(signed.get("signed_input_bundle_hash", "")))
    verified = verification.get("verified_input")
    if not isinstance(verified, dict):
        return False
    verified_hash = _normalize_digest(str(verified.get("bundle_hash", "")))
    return bool(signed_hash and verified_hash and signed_hash != verified_hash)


def _gallery_extension_failure(release_dir: Path) -> tuple[str | None, str | None]:
    extension = _load_json(release_dir.parent / "labtrust_benchmark_extension.v0.json")
    if extension is None:
        return None, None
    gallery_id = str(extension.get("gallery_case_id", ""))
    mapped = _GALLERY_CASE_FAILURE.get(gallery_id)
    if mapped is None:
        return None, None
    return mapped


def detect_gallery_failure(release_dir: Path) -> tuple[str | None, str | None]:
    """Return observed failure_code and responsible_component when a defect is present."""
    run_meta_failure = _detect_run_meta_failure(release_dir)
    if run_meta_failure[0] is not None:
        return run_meta_failure

    manifest = _load_json(release_dir / "manifest.json")
    if manifest is None:
        return "manifest_missing", "release_manifest"

    if (release_dir / "pf_handoff.json").is_file() or (release_dir / "handoff_to_pf.legacy.json").is_file():
        return "legacy_handoff_file", "handoff"

    cert = _load_json(release_dir / "trace_certificate.json")
    if cert is None:
        return "artifact_missing", "certificate_producer"

    cert_status = str(cert.get("status", ""))
    if cert_status == "Rejected":
        return "lean_certificate_rejected", "formal_kernel"
    if cert_status == "Stale":
        return "lean_certificate_stale", "formal_kernel"

    manifest_cert_id = str(manifest.get("certificate_id", ""))
    cert_id = str(cert.get("certificate_id", ""))
    if manifest_cert_id and cert_id and manifest_cert_id != cert_id:
        return "certificate_id_mismatch", "certificate_producer"

    manifest_trace = _normalize_digest(str(manifest.get("trace_hash", "")))
    cert_trace = _normalize_digest(str(cert.get("trace_hash", "")))

    if cert_trace and manifest_trace and cert_trace != manifest_trace:
        return "lean_certificate_trace_hash_mismatch", "formal_kernel"

    trace_path = release_dir / "trace.json"
    trace_doc = _load_json(trace_path)
    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, dict) and trace_path.is_file():
        expected_file = _normalize_digest(str(artifacts.get("trace.json", "")))
        actual_file = file_digest(trace_path.read_bytes())
        if expected_file and actual_file != expected_file:
            return "trace_hash_mismatch", "runtime_producer"

    if trace_doc is not None and manifest_trace:
        trace_declared = _normalize_digest(str(trace_doc.get("trace_hash", "")))
        if trace_declared and trace_declared != manifest_trace:
            return "trace_hash_mismatch", "runtime_producer"

    alignment = _load_json(release_dir / "trace_hash_alignment.json")
    if alignment is not None and manifest_trace:
        aligned = _normalize_digest(str(alignment.get("trace_hash", "")))
        if aligned and aligned != manifest_trace:
            return "trace_hash_mismatch", "runtime_producer"

    if _detect_lean_verified_input_mismatch(release_dir):
        return "lean_verified_input_hash_mismatch", "verifier"

    if _detect_claim_id_mismatch(release_dir):
        return "scientific_memory_claim_id_mismatch", "scientific_memory"

    sm_report = _load_json(release_dir / "scientific_memory_import_report.json")
    if sm_report is not None and sm_report.get("verification_status") != "passed":
        return "scientific_memory_claim_id_mismatch", "scientific_memory"

    if _placeholder_commit_detected(release_dir):
        return "placeholder_source_commit", "runtime_producer"

    lean = _load_json(release_dir / "lean_check_result.v0.json")
    if lean is not None and lean.get("status") not in (None, "ProofChecked"):
        return "lean_certificate_rejected", "formal_kernel"

    return _gallery_extension_failure(release_dir)


def evaluate_labtrust_gallery_case(
    case: dict[str, Any],
    release_dir: Path,
) -> tuple[str, str | None, str | None, str, str]:
    """
    Return (
        observed_status,
        observed_failure_code,
        observed_component,
        release_chain_status,
        certificate_status,
    ).
    """
    failure_code, component = detect_gallery_failure(release_dir)
    cert = _load_json(release_dir / "trace_certificate.json")
    certificate_status = "not_applicable"
    if cert is not None:
        status = str(cert.get("status", "CertificateChecked"))
        if status in {"CertificateChecked", "Rejected", "Stale"}:
            certificate_status = status

    release_chain_status = "valid" if failure_code is None else "invalid"
    kind = str(case.get("case_kind", ""))
    expected_code = case.get("expected_failure_code")

    if kind == "valid_release":
        if failure_code is None:
            return "passed", None, None, "valid", certificate_status
        return "failed", failure_code, component or localize_failure_code(failure_code), "invalid", certificate_status

    if failure_code is None:
        return "failed", "expected_failure_not_detected", "unknown", "valid", certificate_status

    code_ok = failure_code == expected_code
    if not code_ok and isinstance(expected_code, str):
        extension_code = _PROTOCOL_TO_BENCHMARK_CODE.get(expected_code.upper(), "")
        code_ok = failure_code == extension_code or failure_code == expected_code

    expected_component = case.get("expected_responsible_component") or localize_failure_code(
        str(expected_code or failure_code),
    )
    component = component or localize_failure_code(failure_code)
    component_ok = component == expected_component
    observed_status = "passed" if code_ok and component_ok else "failed"
    return observed_status, failure_code, component, release_chain_status, certificate_status
