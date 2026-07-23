"""PF-Core release bundle assembly, validation, and closed-bundle verification."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from pcs_core.asset_resolver import (
    distribution_root,
    pin_path,
    relative_to_distribution,
    require_lean_root,
)
from pcs_core.hash import CANONICALIZATION_VERSION, canonical_hash
from pcs_core.lean_check import compute_proof_term_hash, pfcore_generated_dir
from pcs_core.pf_core_lean_codegen import (
    compute_lean_environment_hash,
    compute_lean_environment_hash_from_bundle,
    pfcore_kernel_lean_paths,
    resolve_certificate_mode,
)
from pcs_core.pf_core_runtime import compute_trace_hash
from pcs_core.safe_paths import UnsafePathError, resolve_contained_file, strip_repo_generated_prefix
from pcs_core.validate import ValidationError, validate_artifact, validate_schema

EVIDENCE_DIR_NAME = "evidence"
EVIDENCE_MANIFEST_NAME = "evidence_manifest.json"
SEMANTIC_PROJECTION_NAME = "PFCoreSemanticProjection.v0.json"
THEOREM_MANIFEST_NAME = "PFCoreTheoremManifest.v0.json"
BUNDLE_VERIFICATION_RESULT_NAME = "PFCoreBundleVerificationResult.v0.json"


@dataclass(frozen=True)
class BundleIssue:
    code: str
    message: str


@dataclass
class BundleValidationResult:
    ok: bool
    bundle_dir: Path
    issues: list[BundleIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "bundle_dir": str(self.bundle_dir),
            "issues": [{"code": i.code, "message": i.message} for i in self.issues],
        }


@dataclass
class BundleVerificationCheck:
    check_id: str
    status: str
    detail: str = ""


@dataclass
class BundleVerificationResult:
    ok: bool
    bundle_dir: Path
    issues: list[BundleIssue] = field(default_factory=list)
    checks: list[BundleVerificationCheck] = field(default_factory=list)
    manifest_digest: str | None = None
    result_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        from pcs_core import __version__

        payload: dict[str, Any] = {
            "schema_version": "v0",
            "artifact_type": "PFCoreBundleVerificationResult.v0",
            "canonicalization_version": CANONICALIZATION_VERSION,
            "ok": self.ok,
            "bundle_dir": str(self.bundle_dir),
            "verifier": "pcs-core",
            "verifier_version": str(__version__),
            "checks": [
                {
                    "check_id": c.check_id,
                    "status": c.status,
                    **({"detail": c.detail} if c.detail else {}),
                }
                for c in self.checks
            ],
            "issues": [{"code": i.code, "message": i.message} for i in self.issues],
            "signature_or_digest": "sha256:" + "0" * 64,
        }
        if self.manifest_digest:
            payload["manifest_digest"] = self.manifest_digest
        payload["signature_or_digest"] = canonical_hash(payload)
        return payload


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object root in {path}")
    return data


def _unique_kernel_paths(manifest: Mapping[str, Any]) -> list[str]:
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise ValueError("kernel manifest files must be a list")
    paths: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("kernel manifest entry must be an object")
        rel = str(entry.get("path") or "")
        if not rel:
            raise ValueError("kernel manifest entry missing path")
        if rel in seen:
            raise ValueError(f"duplicate kernel path: {rel}")
        seen.add(rel)
        paths.append(rel)
    return paths


def _resolve_proof_path(certificate: Mapping[str, Any]) -> Path | None:
    """Resolve certificate proof_term_ref only under lean/PFCore/Generated/."""
    proof_ref = str(certificate.get("proof_term_ref") or certificate.get("proof_ref") or "")
    if not proof_ref:
        return None
    generated_root = pfcore_generated_dir()
    relative = strip_repo_generated_prefix(proof_ref)
    try:
        return resolve_contained_file(
            generated_root,
            relative,
            allowed_suffixes=frozenset({".lean"}),
        )
    except UnsafePathError as exc:
        raise UnsafePathError(
            f"proof_term_ref must resolve under lean/PFCore/Generated/: {exc}"
        ) from exc


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _safe_bundle_dest(bundle_dir: Path, rel: str) -> Path:
    normalized = rel.replace("\\", "/")
    dest = bundle_dir.joinpath(*Path(normalized).parts)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.resolve().relative_to(bundle_dir.resolve())
    except ValueError as exc:
        raise UnsafePathError(f"bundle dest escapes bundle root: {rel}") from exc
    return dest


def collect_tool_versions() -> dict[str, str]:
    """Deterministic tool pins recorded beside release bundles (not hashed into manifest)."""
    from pcs_core import __version__
    from pcs_core.lean_check import lean_dir

    versions: dict[str, str] = {
        "pcs_core": str(__version__),
        "python": platform.python_version(),
    }
    toolchain = lean_dir() / "lean-toolchain"
    if toolchain.is_file():
        versions["lean_toolchain"] = toolchain.read_text(encoding="utf-8").strip()
    elan_pin = pin_path("elan.json", required=False)
    if elan_pin is not None and elan_pin.is_file():
        try:
            pin = json.loads(elan_pin.read_text(encoding="utf-8"))
            if isinstance(pin, dict) and pin.get("version"):
                versions["elan"] = str(pin["version"])
            if isinstance(pin, dict) and pin.get("sha256"):
                versions["elan_sha256"] = str(pin["sha256"])
        except (OSError, json.JSONDecodeError):
            pass
    certifyedge_pin = pin_path("certifyedge.json", required=False)
    if certifyedge_pin is not None and certifyedge_pin.is_file():
        try:
            pin = json.loads(certifyedge_pin.read_text(encoding="utf-8"))
            if isinstance(pin, dict):
                if pin.get("image_digest"):
                    versions["certifyedge_image_digest"] = str(pin["image_digest"])
                if pin.get("version"):
                    versions["certifyedge"] = str(pin["version"])
                if pin.get("status"):
                    versions["certifyedge_pin_status"] = str(pin["status"])
                if pin.get("provision_strategy"):
                    versions["certifyedge_provision_strategy"] = str(pin["provision_strategy"])
                from pcs_core.certifyedge_pin import pin_identity_from

                versions["certifyedge_pin_identity"] = pin_identity_from(pin)
        except (OSError, json.JSONDecodeError):
            pass
    return versions


def write_tool_versions(out_dir: Path) -> Path:
    """Write sidecar tool pin record; excluded from manifest canonical hash."""
    path = out_dir / "tool_versions.json"
    payload = {
        "schema_version": "v0",
        "artifact_type": "PcsToolVersions.v0",
        "tools": collect_tool_versions(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_certifyedge_pin_record(out_dir: Path) -> Path | None:
    """Copy trusted checker pin snapshot into the release bundle."""
    try:
        from pcs_core.certifyedge_pin import certifyedge_pin_record_for_bundle

        record = certifyedge_pin_record_for_bundle()
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    path = out_dir / "certifyedge_pin.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_kernel_manifest() -> dict[str, Any]:
    """Per-file PF-Core kernel manifest for self-contained bundle validation."""
    files: list[dict[str, str]] = []
    for path in pfcore_kernel_lean_paths():
        rel = relative_to_distribution(path)
        files.append({"path": rel, "sha256": _file_sha256(path)})
    manifest: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreKernelManifest.v0",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "files": files,
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    manifest["signature_or_digest"] = canonical_hash(manifest)
    return manifest


def compute_pfcore_kernel_hash_from_manifest(
    manifest: Mapping[str, Any],
    *,
    root: Path,
) -> str:
    """Recompute aggregate kernel hash from manifest-listed files under ``root``."""
    _unique_kernel_paths(manifest)
    entries = manifest.get("files")
    assert isinstance(entries, list)
    parts: list[bytes] = []
    for entry in sorted(entries, key=lambda item: str(item.get("path") or "")):
        if not isinstance(entry, dict):
            raise ValueError("kernel manifest entry must be an object")
        rel = str(entry.get("path") or "")
        expected = str(entry.get("sha256") or "")
        path = resolve_contained_file(root, rel, allowed_suffixes=frozenset({".lean"}))
        content = path.read_bytes()
        actual = _file_sha256(path)
        if expected and actual != expected:
            raise ValueError(f"kernel file hash mismatch for {rel}: {actual} != {expected}")
        parts.append(content)
    digest = hashlib.sha256(b"\n---\n".join(parts)).hexdigest()
    return f"sha256:{digest}"


def _copy_kernel_into_bundle(out_dir: Path, manifest: Mapping[str, Any]) -> None:
    kernel_root = out_dir / "kernel"
    asset_root = distribution_root()
    if asset_root is None:
        from pcs_core.paths import repo_root

        asset_root = repo_root()
    entries = manifest.get("files")
    if not isinstance(entries, list):
        return
    kernel_root.mkdir(parents=True, exist_ok=True)
    kernel_resolved = kernel_root.resolve()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("path") or "")
        if not rel:
            continue
        src = resolve_contained_file(asset_root, rel, allowed_suffixes=frozenset({".lean"}))
        normalized = rel.replace("\\", "/")
        dest_candidate = kernel_root.joinpath(*Path(normalized).parts)
        dest_candidate.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest_candidate.parent.resolve().relative_to(kernel_resolved)
        except ValueError as exc:
            raise UnsafePathError(f"kernel dest escapes bundle: {rel}") from exc
        shutil.copy2(src, dest_candidate)


def _copy_lean_environment_into_bundle(out_dir: Path) -> None:
    """Copy pinned Lean toolchain and lake project files into the bundle root."""
    lean_project = require_lean_root()
    toolchain_src = lean_project / "lean-toolchain"
    if toolchain_src.is_file():
        shutil.copy2(toolchain_src, out_dir / "lean-toolchain")
        dest_toolchain = out_dir / "lean" / "lean-toolchain"
        dest_toolchain.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(toolchain_src, dest_toolchain)
    for rel in ("lakefile.lean", "lake-manifest.json", "PFCore.lean"):
        src = lean_project / rel
        if src.is_file():
            dest = out_dir / "lean" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def compute_evidence_manifest_digest(manifest: Mapping[str, Any]) -> str:
    payload = {k: v for k, v in manifest.items() if k != "evidence_manifest_digest"}
    return canonical_hash(dict(payload))


def build_evidence_manifest(
    *,
    files: list[dict[str, Any]],
    evidence_selection_policy: str,
    evidence_selection_policy_version: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreEvidenceManifest.v0",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "evidence_selection_policy": evidence_selection_policy,
        "evidence_selection_policy_version": evidence_selection_policy_version,
        "files": sorted(files, key=lambda item: str(item.get("path") or "")),
        "evidence_manifest_digest": "sha256:" + "0" * 64,
    }
    body["evidence_manifest_digest"] = compute_evidence_manifest_digest(body)
    return body


def _unique_evidence_basename(preferred: str, used: set[str]) -> str:
    base = Path(preferred).name or "artifact.json"
    if base not in used:
        used.add(base)
        return base
    stem = Path(base).stem
    suffix = Path(base).suffix or ".json"
    index = 2
    while True:
        candidate = f"{stem}_{index}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        index += 1


def _copy_evidence_into_bundle(
    out_dir: Path,
    *,
    trace: Mapping[str, Any],
    trace_path: Path,
    certificate: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    """Copy selected evidence artifacts into ``evidence/`` and write evidence_manifest.

    Returns ``(evidence_manifest_rel, evidence_manifest_hash)``.
    """
    from pcs_core.pf_core_resolved_evidence import (
        EVIDENCE_SELECTION_FILENAME,
        EVIDENCE_SELECTION_POLICY,
        EVIDENCE_SELECTION_POLICY_VERSION,
        EvidenceResolutionError,
        resolve_pf_core_evidence,
    )

    mode = str(
        certificate.get("certificate_mode")
        or resolve_certificate_mode(trace, trace_path=trace_path)
    )
    try:
        evidence = resolve_pf_core_evidence(
            dict(trace),
            trace_path=trace_path,
            certificate_mode=mode,
        )
    except EvidenceResolutionError:
        # Runtime-only bundles may lack selectable evidence; emit empty closed list.
        evidence = None

    evidence_root = out_dir / EVIDENCE_DIR_NAME
    evidence_root.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    files: list[dict[str, Any]] = []

    def _add_file(
        src: Path | None,
        *,
        role: str,
        artifact_id: str | None,
        artifact_type: str | None,
        embedded_payload: Mapping[str, Any] | None = None,
        preferred_name: str | None = None,
    ) -> None:
        if src is not None and src.is_file():
            name = _unique_evidence_basename(preferred_name or src.name, used_names)
            rel = f"{EVIDENCE_DIR_NAME}/{name}"
            dest = _safe_bundle_dest(out_dir, rel)
            shutil.copy2(src, dest)
            entry: dict[str, Any] = {
                "path": rel,
                "sha256": _file_sha256(dest),
                "role": role,
            }
            if artifact_id:
                entry["artifact_id"] = artifact_id
            if artifact_type:
                entry["artifact_type"] = artifact_type
            files.append(entry)
            return
        if embedded_payload is not None:
            name = _unique_evidence_basename(
                preferred_name or f"{role}-{artifact_id or 'embedded'}.json",
                used_names,
            )
            rel = f"{EVIDENCE_DIR_NAME}/{name}"
            dest = _safe_bundle_dest(out_dir, rel)
            dest.write_text(
                json.dumps(dict(embedded_payload), indent=2) + "\n",
                encoding="utf-8",
            )
            entry = {
                "path": rel,
                "sha256": _file_sha256(dest),
                "role": role,
            }
            if artifact_id:
                entry["artifact_id"] = artifact_id
            if artifact_type:
                entry["artifact_type"] = artifact_type
            files.append(entry)

    if evidence is not None:
        for handoff in evidence.handoffs:
            _add_file(
                handoff.path,
                role="handoff",
                artifact_id=handoff.handoff_id,
                artifact_type="PFCoreHandoff.v0",
                embedded_payload=None if handoff.path else handoff.artifact,
                preferred_name=f"handoff-{handoff.handoff_id}.json",
            )
        for contract in evidence.contracts:
            _add_file(
                contract.path,
                role="contract",
                artifact_id=contract.contract_id,
                artifact_type="PFCoreContract.v0",
                embedded_payload=None if contract.path else contract.artifact,
                preferred_name=f"contract-{contract.contract_id}.json",
            )
        if evidence.effect_frame is not None:
            frame_id = str(evidence.effect_frame.get("frame_id") or "effect-frame")
            _add_file(
                evidence.effect_frame_path,
                role="effect_frame",
                artifact_id=frame_id,
                artifact_type="PFCoreEffectFrame.v0",
                embedded_payload=(
                    None if evidence.effect_frame_path else evidence.effect_frame
                ),
                preferred_name=f"effect-frame-{frame_id}.json",
            )
        selection_path = trace_path.parent / EVIDENCE_SELECTION_FILENAME
        if selection_path.is_file() and not isinstance(trace.get("evidence_selection"), Mapping):
            _add_file(
                selection_path,
                role="policy",
                artifact_id="evidence_selection",
                artifact_type="PFCoreEvidenceSelection.v0",
                preferred_name=EVIDENCE_SELECTION_FILENAME,
            )
        elif isinstance(trace.get("evidence_selection"), Mapping):
            _add_file(
                None,
                role="policy",
                artifact_id="evidence_selection",
                artifact_type="PFCoreEvidenceSelection.v0",
                embedded_payload=dict(trace["evidence_selection"]),
                preferred_name=EVIDENCE_SELECTION_FILENAME,
            )
        policy = evidence.evidence_selection_policy
        policy_version = evidence.evidence_selection_policy_version
    else:
        policy = EVIDENCE_SELECTION_POLICY
        policy_version = EVIDENCE_SELECTION_POLICY_VERSION

    manifest = build_evidence_manifest(
        files=files,
        evidence_selection_policy=policy,
        evidence_selection_policy_version=policy_version,
    )
    rel = EVIDENCE_MANIFEST_NAME
    dest = _safe_bundle_dest(out_dir, rel)
    dest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return rel, str(manifest["evidence_manifest_digest"])


def _discover_companion_artifact(
    *,
    name: str,
    certificate_path: Path,
    lean_check_result_path: Path | None,
    proof_path: Path | None,
    artifact_paths_key: str,
) -> Path | None:
    if lean_check_result_path is not None and lean_check_result_path.is_file():
        try:
            result = _load_json(lean_check_result_path)
        except (OSError, json.JSONDecodeError, ValueError):
            result = {}
        paths = result.get("artifact_paths")
        if isinstance(paths, Mapping):
            raw = paths.get(artifact_paths_key)
            if isinstance(raw, str) and raw.strip():
                candidate = Path(raw)
                if candidate.is_file():
                    return candidate.resolve()
    sibling = certificate_path.parent / name
    if sibling.is_file():
        return sibling.resolve()
    if proof_path is not None:
        sibling = proof_path.parent / name
        if sibling.is_file():
            return sibling.resolve()
    return None


def build_release_manifest(
    *,
    trace: Mapping[str, Any],
    certificate: Mapping[str, Any],
    trace_rel: str,
    certificate_rel: str,
    lean_check_result_rel: str | None = None,
    lean_check_result_hash: str | None = None,
    proof_rel: str | None = None,
    semantic_projection_rel: str | None = None,
    semantic_projection_hash: str | None = None,
    theorem_manifest_rel: str | None = None,
    theorem_manifest_hash: str | None = None,
    evidence_manifest_rel: str | None = None,
    evidence_manifest_hash: str | None = None,
    kernel_manifest: Mapping[str, Any] | None = None,
    trace_path: Path | None = None,
    bundle_dir: Path | None = None,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    trace_hash = str(certificate.get("trace_hash") or trace.get("trace_hash") or "")
    if not trace_hash.startswith("sha256:"):
        trace_hash = compute_trace_hash(dict(trace))
    proof_term_hash = str(certificate.get("proof_term_hash") or "")
    kernel_manifest = kernel_manifest or build_kernel_manifest()
    asset_root = distribution_root()
    if asset_root is None:
        from pcs_core.paths import repo_root

        asset_root = repo_root()
    kernel_root = bundle_dir if bundle_dir is not None else asset_root
    kernel_files_root = kernel_root / "kernel" if bundle_dir is not None else asset_root
    claim_class = str(certificate.get("claim_class") or "")
    manifest: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreReleaseBundleManifest.v0",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "trace_path": trace_rel,
        "certificate_path": certificate_rel,
        "trace_hash": trace_hash,
        "kernel_manifest_path": "kernel_manifest.json",
        "pfcore_kernel_hash": compute_pfcore_kernel_hash_from_manifest(
            kernel_manifest,
            root=kernel_files_root,
        ),
        "lean_environment_hash": str(certificate.get("lean_environment_hash") or ""),
        "certificate_mode": certificate.get("certificate_mode")
        or resolve_certificate_mode(trace, trace_path=trace_path),
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    if proof_term_hash.startswith("sha256:"):
        manifest["proof_term_hash"] = proof_term_hash
    if claim_class:
        manifest["claim_class"] = claim_class
    if bundle_dir is not None:
        manifest["lean_environment_hash"] = compute_lean_environment_hash_from_bundle(
            bundle_dir,
            kernel_manifest,
        )
    elif not manifest["lean_environment_hash"]:
        manifest["lean_environment_hash"] = compute_lean_environment_hash()
    if lean_check_result_rel:
        manifest["lean_check_result_path"] = lean_check_result_rel
    if lean_check_result_hash and lean_check_result_hash.startswith("sha256:"):
        manifest["lean_check_result_hash"] = lean_check_result_hash
    if proof_rel:
        manifest["proof_path"] = proof_rel
    if semantic_projection_rel:
        manifest["semantic_projection_path"] = semantic_projection_rel
    if semantic_projection_hash and semantic_projection_hash.startswith("sha256:"):
        manifest["semantic_projection_hash"] = semantic_projection_hash
    if theorem_manifest_rel:
        manifest["theorem_manifest_path"] = theorem_manifest_rel
    if theorem_manifest_hash and theorem_manifest_hash.startswith("sha256:"):
        manifest["theorem_manifest_hash"] = theorem_manifest_hash
    if evidence_manifest_rel:
        manifest["evidence_manifest_path"] = evidence_manifest_rel
    if evidence_manifest_hash and evidence_manifest_hash.startswith("sha256:"):
        manifest["evidence_manifest_hash"] = evidence_manifest_hash
    # LeanKernelChecked requires closed projection/evidence/proof paths.
    if claim_class == "LeanKernelChecked":
        missing: list[str] = []
        for key in (
            "proof_path",
            "lean_check_result_path",
            "lean_check_result_hash",
            "proof_term_hash",
            "semantic_projection_path",
            "semantic_projection_hash",
            "theorem_manifest_path",
            "theorem_manifest_hash",
            "evidence_manifest_path",
            "evidence_manifest_hash",
        ):
            value = str(manifest.get(key) or "")
            if not value or (key.endswith("_hash") and not value.startswith("sha256:")):
                missing.append(key)
        if missing:
            raise ValueError(
                "LeanKernelChecked bundle requires closed fields: " + ", ".join(missing)
            )
    manifest["signature_or_digest"] = canonical_hash(manifest)
    return manifest, kernel_manifest


def bundle_release(
    trace_path: Path,
    cert_path: Path,
    out_dir: Path,
    *,
    lean_check_result_path: Path | None = None,
    semantic_projection_path: Path | None = None,
    theorem_manifest_path: Path | None = None,
) -> Path:
    """Copy trace, certificate, optional LeanCheckResult, proof, projection, evidence, and manifest."""
    trace = _load_json(trace_path)
    certificate = _load_json(cert_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    trace_dest = out_dir / "trace.json"
    cert_dest = out_dir / "certificate.json"
    shutil.copy2(trace_path, trace_dest)
    shutil.copy2(cert_path, cert_dest)

    lean_rel: str | None = None
    lean_hash: str | None = None
    if lean_check_result_path is not None and lean_check_result_path.is_file():
        lean_dest = out_dir / "LeanCheckResult.v0.json"
        shutil.copy2(lean_check_result_path, lean_dest)
        lean_rel = lean_dest.name
        lean_hash = _file_sha256(lean_dest)

    proof_rel: str | None = None
    proof_path = _resolve_proof_path(certificate)
    if proof_path is not None:
        proof_dest = out_dir / proof_path.name
        shutil.copy2(proof_path, proof_dest)
        proof_rel = proof_dest.name

    projection_src = semantic_projection_path or _discover_companion_artifact(
        name=SEMANTIC_PROJECTION_NAME,
        certificate_path=cert_path,
        lean_check_result_path=lean_check_result_path,
        proof_path=proof_path,
        artifact_paths_key="semantic_projection",
    )
    projection_rel: str | None = None
    projection_hash: str | None = None
    if projection_src is not None and projection_src.is_file():
        projection_dest = out_dir / SEMANTIC_PROJECTION_NAME
        shutil.copy2(projection_src, projection_dest)
        projection_rel = projection_dest.name
        try:
            projection_obj = _load_json(projection_dest)
            projection_hash = str(projection_obj.get("projection_hash") or "")
        except (OSError, json.JSONDecodeError, ValueError):
            projection_hash = _file_sha256(projection_dest)
        if not projection_hash.startswith("sha256:"):
            projection_hash = _file_sha256(projection_dest)

    theorem_src = theorem_manifest_path or _discover_companion_artifact(
        name=THEOREM_MANIFEST_NAME,
        certificate_path=cert_path,
        lean_check_result_path=lean_check_result_path,
        proof_path=proof_path,
        artifact_paths_key="theorem_manifest",
    )
    theorem_rel: str | None = None
    theorem_hash: str | None = None
    if theorem_src is not None and theorem_src.is_file():
        theorem_dest = out_dir / THEOREM_MANIFEST_NAME
        shutil.copy2(theorem_src, theorem_dest)
        theorem_rel = theorem_dest.name
        try:
            from pcs_core.pf_core_theorem_manifest import (
                compute_theorem_manifest_digest,
                load_theorem_manifest,
            )

            theorem_obj = load_theorem_manifest(theorem_dest)
            theorem_hash = str(
                theorem_obj.get("theorem_manifest_digest")
                or compute_theorem_manifest_digest(theorem_obj)
            )
        except (OSError, json.JSONDecodeError, ValueError):
            theorem_hash = _file_sha256(theorem_dest)

    evidence_rel, evidence_hash = _copy_evidence_into_bundle(
        out_dir,
        trace=trace,
        trace_path=trace_path,
        certificate=certificate,
    )

    kernel_manifest = build_kernel_manifest()
    _copy_kernel_into_bundle(out_dir, kernel_manifest)
    _copy_lean_environment_into_bundle(out_dir)

    # For LeanKernelChecked, lean-check result is required; synthesize hash if path present.
    claim_class = str(certificate.get("claim_class") or "")
    if claim_class == "LeanKernelChecked" and lean_rel and not lean_hash:
        lean_hash = _file_sha256(out_dir / lean_rel)

    manifest, _kernel_manifest = build_release_manifest(
        trace=trace,
        certificate=certificate,
        trace_rel=trace_dest.name,
        certificate_rel=cert_dest.name,
        lean_check_result_rel=lean_rel,
        lean_check_result_hash=lean_hash,
        proof_rel=proof_rel,
        semantic_projection_rel=projection_rel,
        semantic_projection_hash=projection_hash,
        theorem_manifest_rel=theorem_rel,
        theorem_manifest_hash=theorem_hash,
        evidence_manifest_rel=evidence_rel,
        evidence_manifest_hash=evidence_hash,
        kernel_manifest=kernel_manifest,
        trace_path=trace_path,
        bundle_dir=out_dir,
    )
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    kernel_manifest_path = out_dir / "kernel_manifest.json"
    kernel_manifest_path.write_text(json.dumps(kernel_manifest, indent=2) + "\n", encoding="utf-8")
    write_tool_versions(out_dir)
    write_certifyedge_pin_record(out_dir)
    return manifest_path


def _bundle_resolve(
    bundle_dir: Path,
    rel: str,
    *,
    allowed_suffixes: frozenset[str],
) -> Path:
    return resolve_contained_file(bundle_dir, rel, allowed_suffixes=allowed_suffixes)


def _validate_hashed_json_artifact(
    result: BundleValidationResult,
    *,
    bundle_root: Path,
    rel: str,
    expected_hash: str,
    artifact_type: str | None,
    missing_code: str,
    hash_mismatch_code: str,
    hash_field: str = "projection_hash",
) -> Path | None:
    if not rel:
        return None
    try:
        path = _bundle_resolve(bundle_root, rel, allowed_suffixes=frozenset({".json"}))
    except UnsafePathError as exc:
        result.issues.append(BundleIssue(f"{missing_code}Unsafe", str(exc)))
        return None
    if not path.is_file():
        result.issues.append(BundleIssue(missing_code, f"missing: {rel}"))
        return None
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        result.issues.append(BundleIssue(f"{missing_code}Unreadable", str(exc)))
        return path
    if artifact_type:
        try:
            validate_artifact(payload, artifact_type, release_grade=True)
        except ValidationError as exc:
            for err in exc.errors or [str(exc)]:
                result.issues.append(BundleIssue(f"{missing_code}Invalid", err))
    actual = ""
    declared = ""
    if artifact_type == "PFCoreSemanticProjection.v0":
        actual = str(payload.get("projection_hash") or "")
        declared = actual
    elif artifact_type == "PFCoreTheoremManifest.v0":
        from pcs_core.pf_core_theorem_manifest import compute_theorem_manifest_digest

        declared = str(payload.get("theorem_manifest_digest") or "")
        actual = compute_theorem_manifest_digest(payload)
        if declared and declared != actual:
            result.issues.append(
                BundleIssue(
                    hash_mismatch_code,
                    f"{rel} declared digest {declared!r} != recomputed {actual!r}",
                )
            )
    elif artifact_type == "PFCoreEvidenceManifest.v0":
        declared = str(payload.get("evidence_manifest_digest") or "")
        actual = compute_evidence_manifest_digest(payload)
        if declared and declared != actual:
            result.issues.append(
                BundleIssue(
                    hash_mismatch_code,
                    f"{rel} declared digest {declared!r} != recomputed {actual!r}",
                )
            )
    elif hash_field in payload:
        actual = str(payload.get(hash_field) or "")
    if not actual.startswith("sha256:"):
        actual = _file_sha256(path)
    if expected_hash.startswith("sha256:") and actual != expected_hash:
        result.issues.append(
            BundleIssue(
                hash_mismatch_code,
                f"{rel} hash {actual!r} != manifest {expected_hash!r}",
            )
        )
    return path


def validate_bundle(bundle_dir: Path) -> BundleValidationResult:
    """Validate a PF-Core release bundle directory and manifest hashes.

    Schema validation of the release and kernel manifests runs **before** any
    referenced path is followed. This is the lower-cost structural command;
    stable releases must also run ``verify-bundle``.
    """
    result = BundleValidationResult(ok=False, bundle_dir=bundle_dir)
    try:
        bundle_root = bundle_dir.resolve(strict=True)
    except OSError as exc:
        result.issues.append(BundleIssue("BundleUnreadable", str(exc)))
        return result

    try:
        manifest_path = _bundle_resolve(
            bundle_root, "manifest.json", allowed_suffixes=frozenset({".json"})
        )
    except UnsafePathError as exc:
        result.issues.append(BundleIssue("ManifestMissing", str(exc)))
        return result

    try:
        manifest = _load_json(manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        result.issues.append(BundleIssue("ManifestUnreadable", str(exc)))
        return result

    # Normative: validate closed release-bundle schema before following refs.
    schema_errors = validate_schema(manifest, "PFCoreReleaseBundleManifest.v0")
    for err in schema_errors:
        result.issues.append(BundleIssue("ManifestSchemaInvalid", err))
    if schema_errors:
        result.ok = False
        return result

    try:
        validate_artifact(
            manifest,
            "PFCoreReleaseBundleManifest.v0",
            release_grade=True,
        )
    except ValidationError as exc:
        for err in exc.errors or [str(exc)]:
            result.issues.append(BundleIssue("ManifestInvalid", err))
        result.ok = False
        return result

    kernel_manifest_rel = str(manifest.get("kernel_manifest_path") or "kernel_manifest.json")
    # Validate kernel manifest schema before resolving any of its file paths.
    kernel_manifest_path: Path | None = None
    kernel_manifest: dict[str, Any] | None = None
    try:
        kernel_manifest_path = _bundle_resolve(
            bundle_root, kernel_manifest_rel, allowed_suffixes=frozenset({".json"})
        )
        kernel_manifest = _load_json(kernel_manifest_path)
        kernel_schema_errors = validate_schema(kernel_manifest, "PFCoreKernelManifest.v0")
        for err in kernel_schema_errors:
            result.issues.append(BundleIssue("KernelManifestSchemaInvalid", err))
        if kernel_schema_errors:
            result.ok = False
            return result
        try:
            _unique_kernel_paths(kernel_manifest)
        except ValueError as exc:
            result.issues.append(BundleIssue("KernelManifestDuplicatePath", str(exc)))
            result.ok = False
            return result
        try:
            validate_artifact(
                kernel_manifest,
                "PFCoreKernelManifest.v0",
                release_grade=True,
            )
        except ValidationError as exc:
            for err in exc.errors or [str(exc)]:
                result.issues.append(BundleIssue("KernelManifestInvalid", err))
            result.ok = False
            return result
    except (UnsafePathError, OSError, json.JSONDecodeError, ValueError) as exc:
        result.issues.append(BundleIssue("KernelManifestUnreadable", str(exc)))
        # Continue only for path/hash checks that do not require following kernel files
        # when hashes are absent; otherwise fail closed below.

    trace_rel = str(manifest.get("trace_path") or "trace.json")
    cert_rel = str(manifest.get("certificate_path") or "certificate.json")
    try:
        trace_path = _bundle_resolve(bundle_root, trace_rel, allowed_suffixes=frozenset({".json"}))
    except UnsafePathError as exc:
        result.issues.append(BundleIssue("TracePathUnsafe", str(exc)))
        trace_path = None
    try:
        cert_path = _bundle_resolve(bundle_root, cert_rel, allowed_suffixes=frozenset({".json"}))
    except UnsafePathError as exc:
        result.issues.append(BundleIssue("CertificatePathUnsafe", str(exc)))
        cert_path = None

    if trace_path is None:
        result.issues.append(BundleIssue("TraceMissing", f"trace file missing: {trace_rel}"))
    if cert_path is None:
        result.issues.append(BundleIssue("CertificateMissing", f"certificate missing: {cert_rel}"))

    manifest_trace_hash = str(manifest.get("trace_hash") or "")
    manifest_proof_hash = str(manifest.get("proof_term_hash") or "")
    manifest_kernel_hash = str(manifest.get("pfcore_kernel_hash") or "")
    manifest_env_hash = str(manifest.get("lean_environment_hash") or "")

    if trace_path is not None and trace_path.is_file():
        try:
            trace = _load_json(trace_path)
            actual_trace_hash = str(trace.get("trace_hash") or compute_trace_hash(trace))
            if manifest_trace_hash and actual_trace_hash != manifest_trace_hash:
                result.issues.append(
                    BundleIssue(
                        "TraceHashMismatch",
                        f"trace hash {actual_trace_hash!r} != manifest {manifest_trace_hash!r}",
                    )
                )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            result.issues.append(BundleIssue("TraceUnreadable", str(exc)))

    if cert_path is not None and cert_path.is_file():
        try:
            certificate = _load_json(cert_path)
            cert_trace_hash = str(certificate.get("trace_hash") or "")
            if manifest_trace_hash and cert_trace_hash and cert_trace_hash != manifest_trace_hash:
                result.issues.append(
                    BundleIssue(
                        "CertificateTraceHashMismatch",
                        f"certificate trace_hash {cert_trace_hash!r} != manifest",
                    )
                )
            cert_proof_hash = str(certificate.get("proof_term_hash") or "")
            if manifest_proof_hash and cert_proof_hash and cert_proof_hash != manifest_proof_hash:
                result.issues.append(
                    BundleIssue(
                        "ProofTermHashMismatch",
                        f"certificate proof_term_hash {cert_proof_hash!r} != manifest",
                    )
                )
            try:
                validate_artifact(certificate, "PFCoreCertificate.v0", release_grade=True)
            except ValidationError as exc:
                for err in exc.errors or [str(exc)]:
                    result.issues.append(BundleIssue("CertificateInvalid", err))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            result.issues.append(BundleIssue("CertificateUnreadable", str(exc)))

    proof_rel = str(manifest.get("proof_path") or "")
    if proof_rel:
        try:
            proof_path = _bundle_resolve(
                bundle_root, proof_rel, allowed_suffixes=frozenset({".lean"})
            )
        except UnsafePathError as exc:
            result.issues.append(BundleIssue("ProofPathUnsafe", str(exc)))
            proof_path = None
        if proof_path is None:
            result.issues.append(BundleIssue("ProofMissing", f"proof file missing: {proof_rel}"))
        elif manifest_proof_hash.startswith("sha256:"):
            actual = compute_proof_term_hash(proof_path)
            if actual != manifest_proof_hash:
                result.issues.append(
                    BundleIssue(
                        "ProofFileHashMismatch",
                        f"proof file hash {actual!r} != manifest {manifest_proof_hash!r}",
                    )
                )

    lean_check_rel = str(manifest.get("lean_check_result_path") or "")
    lean_check_hash = str(manifest.get("lean_check_result_hash") or "")
    if lean_check_rel:
        try:
            lean_path = _bundle_resolve(
                bundle_root, lean_check_rel, allowed_suffixes=frozenset({".json"})
            )
            if lean_check_hash.startswith("sha256:"):
                actual_lean = _file_sha256(lean_path)
                if actual_lean != lean_check_hash:
                    result.issues.append(
                        BundleIssue(
                            "LeanCheckResultHashMismatch",
                            f"lean check result hash {actual_lean!r} != manifest "
                            f"{lean_check_hash!r}",
                        )
                    )
        except UnsafePathError as exc:
            result.issues.append(BundleIssue("LeanCheckResultPathUnsafe", str(exc)))

    _validate_hashed_json_artifact(
        result,
        bundle_root=bundle_root,
        rel=str(manifest.get("semantic_projection_path") or ""),
        expected_hash=str(manifest.get("semantic_projection_hash") or ""),
        artifact_type="PFCoreSemanticProjection.v0",
        missing_code="SemanticProjection",
        hash_mismatch_code="SemanticProjectionHashMismatch",
    )
    _validate_hashed_json_artifact(
        result,
        bundle_root=bundle_root,
        rel=str(manifest.get("theorem_manifest_path") or ""),
        expected_hash=str(manifest.get("theorem_manifest_hash") or ""),
        artifact_type="PFCoreTheoremManifest.v0",
        missing_code="TheoremManifest",
        hash_mismatch_code="TheoremManifestHashMismatch",
    )
    evidence_path = _validate_hashed_json_artifact(
        result,
        bundle_root=bundle_root,
        rel=str(manifest.get("evidence_manifest_path") or ""),
        expected_hash=str(manifest.get("evidence_manifest_hash") or ""),
        artifact_type="PFCoreEvidenceManifest.v0",
        missing_code="EvidenceManifest",
        hash_mismatch_code="EvidenceManifestHashMismatch",
    )
    if evidence_path is not None and evidence_path.is_file():
        try:
            evidence_manifest = _load_json(evidence_path)
            entries = evidence_manifest.get("files")
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, Mapping):
                        continue
                    rel = str(entry.get("path") or "")
                    expected = str(entry.get("sha256") or "")
                    if not rel:
                        continue
                    try:
                        file_path = _bundle_resolve(
                            bundle_root, rel, allowed_suffixes=frozenset({".json"})
                        )
                    except UnsafePathError as exc:
                        result.issues.append(BundleIssue("EvidencePathUnsafe", str(exc)))
                        continue
                    actual = _file_sha256(file_path)
                    if expected.startswith("sha256:") and actual != expected:
                        result.issues.append(
                            BundleIssue(
                                "EvidenceFileHashMismatch",
                                f"evidence file {rel} hash {actual!r} != {expected!r}",
                            )
                        )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            result.issues.append(BundleIssue("EvidenceManifestUnreadable", str(exc)))

    if manifest_kernel_hash.startswith("sha256:"):
        try:
            if kernel_manifest is None:
                raise FileNotFoundError("kernel_manifest.json not found in bundle")
            actual_kernel = compute_pfcore_kernel_hash_from_manifest(
                kernel_manifest,
                root=bundle_root / "kernel",
            )
        except (
            OSError,
            json.JSONDecodeError,
            ValueError,
            FileNotFoundError,
            UnsafePathError,
        ) as exc:
            result.issues.append(BundleIssue("KernelManifestInvalid", str(exc)))
            actual_kernel = ""
        if actual_kernel and actual_kernel != manifest_kernel_hash:
            result.issues.append(
                BundleIssue(
                    "PfcoreKernelHashMismatch",
                    f"current kernel {actual_kernel!r} != manifest {manifest_kernel_hash!r}",
                )
            )

    if manifest_env_hash.startswith("sha256:"):
        try:
            if kernel_manifest is None:
                raise FileNotFoundError("kernel_manifest.json not found in bundle")
            actual_env = compute_lean_environment_hash_from_bundle(bundle_root, kernel_manifest)
        except (
            OSError,
            json.JSONDecodeError,
            ValueError,
            FileNotFoundError,
            UnsafePathError,
        ) as exc:
            result.issues.append(BundleIssue("LeanEnvironmentInvalid", str(exc)))
            actual_env = ""
        if actual_env and actual_env != manifest_env_hash:
            result.issues.append(
                BundleIssue(
                    "LeanEnvironmentHashMismatch",
                    f"current env {actual_env!r} != manifest {manifest_env_hash!r}",
                )
            )

    expected_digest = canonical_hash(manifest)
    actual_digest = str(manifest.get("signature_or_digest") or "")
    if actual_digest and actual_digest != expected_digest:
        result.issues.append(
            BundleIssue(
                "ManifestDigestMismatch",
                f"manifest digest {actual_digest!r} != recomputed {expected_digest!r}",
            )
        )

    # Sidecar external attestation / preview absence notice (not part of closed digest).
    from pcs_core.external_attestation import (
        ABSENCE_NOTICE_NAME,
        EXTERNAL_ATTESTATION_NAME,
        validate_bundle_external_attestation,
    )

    attest_path = bundle_root / EXTERNAL_ATTESTATION_NAME
    notice_path = bundle_root / ABSENCE_NOTICE_NAME
    if attest_path.is_file() or notice_path.is_file():
        require_live = os.environ.get("PF_CORE_CERTIFYEDGE_REQUIRE_LIVE", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        release_mode = os.environ.get("PCS_RELEASE_MODE", "preview").strip().lower()
        allow_absence = release_mode in {"preview", "dev"} and not require_live
        for err in validate_bundle_external_attestation(
            bundle_root,
            require_live=require_live or release_mode == "release",
            allow_absence_notice=allow_absence,
        ):
            result.issues.append(BundleIssue("ExternalAttestationInvalid", err))

    result.ok = not result.issues
    return result


def _record_check(
    result: BundleVerificationResult,
    check_id: str,
    *,
    ok: bool,
    detail: str = "",
    skipped: bool = False,
) -> None:
    if skipped:
        status = "skipped"
    else:
        status = "passed" if ok else "failed"
    result.checks.append(BundleVerificationCheck(check_id, status, detail))


def _stage_evidence_for_resolve(bundle_root: Path, evidence_manifest: Mapping[str, Any]) -> Path:
    """Stage trace + evidence siblings so resolve_pf_core_evidence can rediscover them."""
    staging = Path(tempfile.mkdtemp(prefix="pfcore-verify-evidence-"))
    trace_rel = "trace.json"
    shutil.copy2(bundle_root / trace_rel, staging / "trace.json")
    entries = evidence_manifest.get("files")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            rel = str(entry.get("path") or "")
            if not rel:
                continue
            src = _bundle_resolve(bundle_root, rel, allowed_suffixes=frozenset({".json"}))
            role = str(entry.get("role") or "")
            dest_name = src.name
            if role == "policy" and dest_name != "evidence_selection.json":
                dest_name = "evidence_selection.json"
            shutil.copy2(src, staging / dest_name)
    return staging


def ensure_bundled_lean_toolchain(bundle_root: Path) -> tuple[bool, str]:
    """Install or select the Lean toolchain pinned in the bundle."""
    toolchain_path = bundle_root / "lean-toolchain"
    if not toolchain_path.is_file():
        toolchain_path = bundle_root / "lean" / "lean-toolchain"
    if not toolchain_path.is_file():
        return False, "bundle missing lean-toolchain"
    toolchain = toolchain_path.read_text(encoding="utf-8").strip()
    if not toolchain:
        return False, "empty lean-toolchain pin"
    elan = shutil.which("elan")
    if elan:
        proc = subprocess.run(
            [elan, "toolchain", "install", toolchain],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            # Already installed is fine; elan may still return non-zero for some pins.
            if "is already installed" not in detail.lower() and "already installed" not in detail.lower():
                # Fall through: lake may still resolve via PATH / lean-toolchain file.
                return True, f"elan install warning: {detail or 'non-zero'}; continuing with lake"
        return True, f"toolchain ready: {toolchain}"
    if shutil.which("lake") or (platform.system() == "Windows" and shutil.which("wsl")):
        return True, f"elan unavailable; using lake with pin {toolchain}"
    return False, "neither elan nor lake available to select Lean toolchain"


def compile_bundled_proof(bundle_root: Path, proof_rel: str) -> tuple[bool, str]:
    """Compile the bundled generated proof against the bundled PF-Core kernel."""
    from pcs_core.lean_check import _run_lake

    try:
        proof_src = _bundle_resolve(
            bundle_root, proof_rel, allowed_suffixes=frozenset({".lean"})
        )
    except UnsafePathError as exc:
        return False, str(exc)

    work = Path(tempfile.mkdtemp(prefix="pfcore-verify-lean-"))
    try:
        # Lake project root
        for name in ("lakefile.lean", "lake-manifest.json", "PFCore.lean"):
            src = bundle_root / "lean" / name
            if src.is_file():
                shutil.copy2(src, work / name)
        toolchain = bundle_root / "lean-toolchain"
        if not toolchain.is_file():
            toolchain = bundle_root / "lean" / "lean-toolchain"
        if toolchain.is_file():
            shutil.copy2(toolchain, work / "lean-toolchain")

        kernel_root = bundle_root / "kernel"
        pfcore_src = kernel_root / "lean" / "PFCore"
        if not pfcore_src.is_dir():
            return False, "bundled kernel missing lean/PFCore"
        shutil.copytree(pfcore_src, work / "PFCore")
        generated = work / "PFCore" / "Generated"
        generated.mkdir(parents=True, exist_ok=True)
        proof_dest = generated / proof_src.name
        shutil.copy2(proof_src, proof_dest)

        if not (work / "lakefile.lean").is_file():
            return False, "bundle missing lean/lakefile.lean"
        if not (work / "PFCore.lean").is_file():
            return False, "bundle missing lean/PFCore.lean"
        if not shutil.which("lake") and not (
            platform.system() == "Windows" and shutil.which("wsl")
        ):
            return False, "lake executable not found"

        build = _run_lake(["build", "PFCore"], cwd=work)
        if build.returncode != 0:
            detail = (build.stderr or build.stdout or "").strip()
            return False, detail or "lake build PFCore failed against bundled kernel"

        rel = Path("PFCore") / "Generated" / proof_src.name
        compile_proc = _run_lake(["env", "lean", rel.as_posix()], cwd=work)
        if compile_proc.returncode != 0:
            detail = (compile_proc.stderr or compile_proc.stdout or "").strip()
            return False, detail or "lake env lean failed on bundled proof"
        return True, "ok"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def verify_bundle(
    bundle_dir: Path,
    *,
    skip_lean_compile: bool = False,
    result_out: Path | None = None,
) -> BundleVerificationResult:
    """Independently verify a closed PF-Core release bundle.

    Performs structural validation, containment path resolution, digest checks,
    semantic-projection replay, theorem-metadata reconstruction, certificate
    comparison, Lean toolchain selection, bundled-kernel proof compile, and
    external attestation checks when present. Emits a digest-bound verification
    result. ``validate-bundle`` remains the cheaper structural-only command;
    stable releases must require ``verify-bundle``.
    """
    result = BundleVerificationResult(ok=False, bundle_dir=bundle_dir)
    structural = validate_bundle(bundle_dir)
    for issue in structural.issues:
        result.issues.append(issue)
    _record_check(
        result,
        "validate_closed_manifests",
        ok=structural.ok,
        detail="validate-bundle structural checks",
    )
    if not structural.ok:
        result.ok = False
        _write_verification_result(result, result_out)
        return result

    try:
        bundle_root = bundle_dir.resolve(strict=True)
        manifest = _load_json(bundle_root / "manifest.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        result.issues.append(BundleIssue("ManifestUnreadable", str(exc)))
        _record_check(result, "load_manifest", ok=False, detail=str(exc))
        _write_verification_result(result, result_out)
        return result

    result.manifest_digest = str(manifest.get("signature_or_digest") or "")
    claim_class = str(manifest.get("claim_class") or "")
    certificate = _load_json(
        _bundle_resolve(
            bundle_root,
            str(manifest.get("certificate_path") or "certificate.json"),
            allowed_suffixes=frozenset({".json"}),
        )
    )
    trace = _load_json(
        _bundle_resolve(
            bundle_root,
            str(manifest.get("trace_path") or "trace.json"),
            allowed_suffixes=frozenset({".json"}),
        )
    )

    # Certificate digest binding compare
    try:
        validate_artifact(certificate, "PFCoreCertificate.v0", release_grade=True)
        recomputed_cert_digest = canonical_hash(dict(certificate))
        declared = str(certificate.get("signature_or_digest") or "")
        cert_ok = (not declared) or declared == recomputed_cert_digest
        if not cert_ok:
            result.issues.append(
                BundleIssue(
                    "CertificateDigestMismatch",
                    f"certificate digest {declared!r} != recomputed {recomputed_cert_digest!r}",
                )
            )
        # Compare certificate digests against closed manifest / bundled files
        for field, manifest_key in (
            ("trace_hash", "trace_hash"),
            ("proof_term_hash", "proof_term_hash"),
            ("lean_environment_hash", "lean_environment_hash"),
            ("pfcore_kernel_hash", "pfcore_kernel_hash"),
            ("semantic_projection_hash", "semantic_projection_hash"),
            ("theorem_manifest_hash", "theorem_manifest_hash"),
        ):
            cert_val = str(certificate.get(field) or "")
            man_val = str(manifest.get(manifest_key) or "")
            if cert_val.startswith("sha256:") and man_val.startswith("sha256:") and cert_val != man_val:
                result.issues.append(
                    BundleIssue(
                        "CertificateManifestFieldMismatch",
                        f"certificate.{field} {cert_val!r} != manifest.{manifest_key} {man_val!r}",
                    )
                )
                cert_ok = False
        _record_check(result, "compare_certificate", ok=cert_ok)
    except ValidationError as exc:
        for err in exc.errors or [str(exc)]:
            result.issues.append(BundleIssue("CertificateInvalid", err))
        _record_check(result, "compare_certificate", ok=False, detail=str(exc))

    # Projection replay
    projection_rel = str(manifest.get("semantic_projection_path") or "")
    projection_hash = str(manifest.get("semantic_projection_hash") or "")
    replay_ok = True
    if projection_rel:
        try:
            projection_path = _bundle_resolve(
                bundle_root, projection_rel, allowed_suffixes=frozenset({".json"})
            )
            stored_projection = _load_json(projection_path)
            evidence_rel = str(manifest.get("evidence_manifest_path") or "")
            evidence_manifest = (
                _load_json(
                    _bundle_resolve(
                        bundle_root, evidence_rel, allowed_suffixes=frozenset({".json"})
                    )
                )
                if evidence_rel
                else {"files": []}
            )
            staging = _stage_evidence_for_resolve(bundle_root, evidence_manifest)
            try:
                from pcs_core.pf_core_resolved_evidence import resolve_pf_core_evidence
                from pcs_core.pf_core_semantic_projection import build_semantic_projection

                staged_trace = staging / "trace.json"
                staged_data = _load_json(staged_trace)
                mode = str(
                    certificate.get("certificate_mode")
                    or manifest.get("certificate_mode")
                    or ""
                )
                resolved = resolve_pf_core_evidence(
                    staged_data,
                    trace_path=staged_trace,
                    certificate_mode=mode,
                )
                replayed = build_semantic_projection(
                    staged_data,
                    certificate_mode=mode,
                    trace_path=staged_trace,
                    resolved_evidence=resolved,
                )
                replay_hash = str(replayed.get("projection_hash") or "")
                stored_hash = str(stored_projection.get("projection_hash") or projection_hash)
                if replay_hash and stored_hash and replay_hash != stored_hash:
                    replay_ok = False
                    result.issues.append(
                        BundleIssue(
                            "ProjectionReplayMismatch",
                            f"replayed {replay_hash!r} != stored {stored_hash!r}",
                        )
                    )
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        except Exception as exc:  # noqa: BLE001
            replay_ok = False
            result.issues.append(BundleIssue("ProjectionReplayFailed", str(exc)))
        _record_check(result, "replay_semantic_projection", ok=replay_ok)
    else:
        _record_check(
            result,
            "replay_semantic_projection",
            ok=True,
            skipped=claim_class != "LeanKernelChecked",
            detail="no semantic projection in bundle",
        )

    # Reconstruct theorem metadata from bundled proof and compare to theorem manifest
    theorem_rel = str(manifest.get("theorem_manifest_path") or "")
    proof_rel = str(manifest.get("proof_path") or "")
    theorem_ok = True
    if theorem_rel and proof_rel:
        try:
            from pcs_core.pf_core_theorem_manifest import (
                load_theorem_manifest,
                propositions_by_name,
                reconstruct_theorem_metadata_from_proof,
            )

            theorem_manifest = load_theorem_manifest(
                _bundle_resolve(
                    bundle_root, theorem_rel, allowed_suffixes=frozenset({".json"})
                )
            )
            proof_text = _bundle_resolve(
                bundle_root, proof_rel, allowed_suffixes=frozenset({".lean"})
            ).read_text(encoding="utf-8")
            reconstructed = reconstruct_theorem_metadata_from_proof(proof_text)
            expected = propositions_by_name(theorem_manifest)
            if set(reconstructed) != set(expected):
                theorem_ok = False
                result.issues.append(
                    BundleIssue(
                        "TheoremMetadataNameDrift",
                        f"proof theorems {sorted(reconstructed)} != "
                        f"manifest {sorted(expected)}",
                    )
                )
            for name, prop in expected.items():
                if name in reconstructed and reconstructed[name] != prop:
                    theorem_ok = False
                    result.issues.append(
                        BundleIssue(
                            "TheoremMetadataPropositionDrift",
                            f"theorem {name!r} proposition drifted vs reconstructed proof text",
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            theorem_ok = False
            result.issues.append(BundleIssue("TheoremMetadataReconstructFailed", str(exc)))
        _record_check(result, "reconstruct_theorem_metadata", ok=theorem_ok)
    else:
        _record_check(
            result,
            "reconstruct_theorem_metadata",
            ok=True,
            skipped=claim_class != "LeanKernelChecked",
            detail="theorem manifest or proof absent",
        )

    # Toolchain + compile
    toolchain_ok, toolchain_detail = ensure_bundled_lean_toolchain(bundle_root)
    if not toolchain_ok:
        result.issues.append(BundleIssue("LeanToolchainUnavailable", toolchain_detail))
    _record_check(result, "select_lean_toolchain", ok=toolchain_ok, detail=toolchain_detail)

    if skip_lean_compile or not proof_rel:
        _record_check(
            result,
            "compile_bundled_proof",
            ok=True,
            skipped=True,
            detail="skipped" if skip_lean_compile else "no proof_path",
        )
    else:
        compile_ok, compile_detail = compile_bundled_proof(bundle_root, proof_rel)
        if not compile_ok:
            result.issues.append(BundleIssue("BundledProofCompileFailed", compile_detail))
        _record_check(
            result,
            "compile_bundled_proof",
            ok=compile_ok,
            detail=compile_detail[:500],
        )

    # External attestation when present / required
    from pcs_core.external_attestation import (
        ABSENCE_NOTICE_NAME,
        EXTERNAL_ATTESTATION_NAME,
        validate_bundle_external_attestation,
    )

    attest_path = bundle_root / EXTERNAL_ATTESTATION_NAME
    notice_path = bundle_root / ABSENCE_NOTICE_NAME
    require_live = os.environ.get("PF_CORE_CERTIFYEDGE_REQUIRE_LIVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    release_mode = os.environ.get("PCS_RELEASE_MODE", "preview").strip().lower()
    allow_absence = release_mode in {"preview", "dev"} and not require_live
    if attest_path.is_file() or notice_path.is_file() or require_live or release_mode == "release":
        attest_errors = validate_bundle_external_attestation(
            bundle_root,
            require_live=require_live or release_mode == "release",
            allow_absence_notice=allow_absence,
        )
        attest_ok = not attest_errors
        for err in attest_errors:
            result.issues.append(BundleIssue("ExternalAttestationInvalid", err))
        _record_check(
            result,
            "verify_external_attestation",
            ok=attest_ok,
            detail="required" if (require_live or release_mode == "release") else "present",
        )
    else:
        _record_check(
            result,
            "verify_external_attestation",
            ok=True,
            skipped=True,
            detail="no attestation sidecar and not required",
        )

    result.ok = not result.issues
    _write_verification_result(result, result_out)
    return result


def _write_verification_result(
    result: BundleVerificationResult,
    result_out: Path | None,
) -> None:
    payload = result.to_dict()
    try:
        validate_artifact(payload, "PFCoreBundleVerificationResult.v0")
    except ValidationError:
        # Still emit digest-bound payload for debugging even if schema drifts.
        pass
    dest = result_out
    if dest is None:
        try:
            dest = result.bundle_dir / BUNDLE_VERIFICATION_RESULT_NAME
        except Exception:  # noqa: BLE001
            return
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        result.result_path = dest
    except OSError:
        return
