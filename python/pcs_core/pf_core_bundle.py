"""PF-Core release bundle assembly and validation."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from pcs_core.hash import canonical_hash
from pcs_core.lean_check import compute_proof_term_hash
from pcs_core.paths import repo_root
from pcs_core.pf_core_lean_codegen import (
    compute_lean_environment_hash,
    compute_pfcore_kernel_hash,
    pfcore_kernel_lean_paths,
    resolve_certificate_mode,
)
from pcs_core.pf_core_runtime import compute_trace_hash
from pcs_core.validate import ValidationError, validate_artifact


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


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object root in {path}")
    return data


def _resolve_proof_path(certificate: Mapping[str, Any]) -> Path | None:
    proof_ref = str(certificate.get("proof_term_ref") or certificate.get("proof_ref") or "")
    if not proof_ref:
        return None
    candidate = repo_root() / proof_ref.replace("\\", "/")
    if candidate.is_file():
        return candidate.resolve()
    path = Path(proof_ref)
    if path.is_file():
        return path.resolve()
    return None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def build_kernel_manifest() -> dict[str, Any]:
    """Per-file PF-Core kernel manifest for self-contained bundle validation."""
    files: list[dict[str, str]] = []
    for path in pfcore_kernel_lean_paths():
        rel = path.relative_to(repo_root()).as_posix()
        files.append({"path": rel, "sha256": _file_sha256(path)})
    return {
        "schema_version": "v0",
        "artifact_type": "PFCoreKernelManifest.v0",
        "files": files,
    }


def compute_pfcore_kernel_hash_from_manifest(
    manifest: Mapping[str, Any],
    *,
    root: Path,
) -> str:
    """Recompute aggregate kernel hash from manifest-listed files under ``root``."""
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise ValueError("kernel manifest files must be a list")
    parts: list[bytes] = []
    for entry in sorted(entries, key=lambda item: str(item.get("path") or "")):
        if not isinstance(entry, dict):
            raise ValueError("kernel manifest entry must be an object")
        rel = str(entry.get("path") or "")
        expected = str(entry.get("sha256") or "")
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(f"kernel file missing under bundle: {rel}")
        content = path.read_bytes()
        actual = _file_sha256(path)
        if expected and actual != expected:
            raise ValueError(f"kernel file hash mismatch for {rel}: {actual} != {expected}")
        parts.append(content)
    digest = hashlib.sha256(b"\n---\n".join(parts)).hexdigest()
    return f"sha256:{digest}"


def _copy_kernel_into_bundle(out_dir: Path, manifest: Mapping[str, Any]) -> None:
    kernel_root = out_dir / "kernel"
    entries = manifest.get("files")
    if not isinstance(entries, list):
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("path") or "")
        if not rel:
            continue
        src = repo_root() / rel
        dest = kernel_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def build_release_manifest(
    *,
    trace: Mapping[str, Any],
    certificate: Mapping[str, Any],
    trace_rel: str,
    certificate_rel: str,
    lean_check_result_rel: str | None = None,
    proof_rel: str | None = None,
    kernel_manifest: Mapping[str, Any] | None = None,
    trace_path: Path | None = None,
) -> dict[str, Any]:
    trace_hash = str(certificate.get("trace_hash") or trace.get("trace_hash") or "")
    if not trace_hash.startswith("sha256:"):
        trace_hash = compute_trace_hash(dict(trace))
    proof_term_hash = str(certificate.get("proof_term_hash") or "")
    kernel_manifest = kernel_manifest or build_kernel_manifest()
    manifest: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreReleaseBundleManifest.v0",
        "trace_path": trace_rel,
        "certificate_path": certificate_rel,
        "trace_hash": trace_hash,
        "proof_term_hash": proof_term_hash,
        "kernel_manifest_path": "kernel_manifest.json",
        "pfcore_kernel_hash": compute_pfcore_kernel_hash_from_manifest(
            kernel_manifest,
            root=repo_root(),
        ),
        "lean_environment_hash": str(
            certificate.get("lean_environment_hash") or compute_lean_environment_hash()
        ),
        "certificate_mode": certificate.get("certificate_mode")
        or resolve_certificate_mode(trace, trace_path=trace_path),
        "signature_or_digest": "sha256:" + "0" * 64,
    }
    if lean_check_result_rel:
        manifest["lean_check_result_path"] = lean_check_result_rel
    if proof_rel:
        manifest["proof_path"] = proof_rel
    manifest["signature_or_digest"] = canonical_hash(manifest)
    return manifest, kernel_manifest


def bundle_release(
    trace_path: Path,
    cert_path: Path,
    out_dir: Path,
    *,
    lean_check_result_path: Path | None = None,
) -> Path:
    """Copy trace, certificate, optional LeanCheckResult, proof file, and manifest."""
    trace = _load_json(trace_path)
    certificate = _load_json(cert_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    trace_dest = out_dir / "trace.json"
    cert_dest = out_dir / "certificate.json"
    shutil.copy2(trace_path, trace_dest)
    shutil.copy2(cert_path, cert_dest)

    lean_rel: str | None = None
    if lean_check_result_path is not None and lean_check_result_path.is_file():
        lean_dest = out_dir / "LeanCheckResult.v0.json"
        shutil.copy2(lean_check_result_path, lean_dest)
        lean_rel = lean_dest.name

    proof_rel: str | None = None
    proof_path = _resolve_proof_path(certificate)
    if proof_path is not None:
        proof_dest = out_dir / proof_path.name
        shutil.copy2(proof_path, proof_dest)
        proof_rel = proof_dest.name

    manifest, kernel_manifest = build_release_manifest(
        trace=trace,
        certificate=certificate,
        trace_rel=trace_dest.name,
        certificate_rel=cert_dest.name,
        lean_check_result_rel=lean_rel,
        proof_rel=proof_rel,
        trace_path=trace_path,
    )
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    kernel_manifest_path = out_dir / "kernel_manifest.json"
    kernel_manifest_path.write_text(json.dumps(kernel_manifest, indent=2) + "\n", encoding="utf-8")
    _copy_kernel_into_bundle(out_dir, kernel_manifest)
    return manifest_path


def validate_bundle(bundle_dir: Path) -> BundleValidationResult:
    """Validate a PF-Core release bundle directory and manifest hashes."""
    result = BundleValidationResult(ok=False, bundle_dir=bundle_dir)
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        result.issues.append(BundleIssue("ManifestMissing", "manifest.json not found"))
        return result

    try:
        manifest = _load_json(manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        result.issues.append(BundleIssue("ManifestUnreadable", str(exc)))
        return result

    trace_rel = str(manifest.get("trace_path") or "trace.json")
    cert_rel = str(manifest.get("certificate_path") or "certificate.json")
    trace_path = bundle_dir / trace_rel
    cert_path = bundle_dir / cert_rel

    if not trace_path.is_file():
        result.issues.append(BundleIssue("TraceMissing", f"trace file missing: {trace_rel}"))
    if not cert_path.is_file():
        result.issues.append(BundleIssue("CertificateMissing", f"certificate missing: {cert_rel}"))

    manifest_trace_hash = str(manifest.get("trace_hash") or "")
    manifest_proof_hash = str(manifest.get("proof_term_hash") or "")
    manifest_kernel_hash = str(manifest.get("pfcore_kernel_hash") or "")
    manifest_env_hash = str(manifest.get("lean_environment_hash") or "")

    if trace_path.is_file():
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

    if cert_path.is_file():
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
                validate_artifact(certificate, "PFCoreCertificate.v0")
            except ValidationError as exc:
                for err in exc.errors or [str(exc)]:
                    result.issues.append(BundleIssue("CertificateInvalid", err))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            result.issues.append(BundleIssue("CertificateUnreadable", str(exc)))

    proof_rel = str(manifest.get("proof_path") or "")
    if proof_rel:
        proof_path = bundle_dir / proof_rel
        if not proof_path.is_file():
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

    if manifest_kernel_hash.startswith("sha256:"):
        kernel_manifest_path = bundle_dir / str(
            manifest.get("kernel_manifest_path") or "kernel_manifest.json"
        )
        try:
            if kernel_manifest_path.is_file():
                kernel_manifest = _load_json(kernel_manifest_path)
                actual_kernel = compute_pfcore_kernel_hash_from_manifest(
                    kernel_manifest,
                    root=bundle_dir / "kernel",
                )
            else:
                actual_kernel = compute_pfcore_kernel_hash()
        except (OSError, json.JSONDecodeError, ValueError, FileNotFoundError) as exc:
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
        kernel_manifest_path = bundle_dir / str(
            manifest.get("kernel_manifest_path") or "kernel_manifest.json"
        )
        try:
            if kernel_manifest_path.is_file():
                kernel_manifest = _load_json(kernel_manifest_path)
                env_parts: list[bytes] = []
                lean_root = repo_root() / "lean"
                toolchain = repo_root() / "lean-toolchain"
                if toolchain.is_file():
                    env_parts.append(toolchain.read_bytes())
                for rel in ("lakefile.lean", "lake-manifest.json"):
                    path = lean_root / rel
                    if path.is_file():
                        env_parts.append(path.read_bytes())
                entries = kernel_manifest.get("files")
                if isinstance(entries, list):
                    for entry in sorted(entries, key=lambda item: str(item.get("path") or "")):
                        if not isinstance(entry, dict):
                            continue
                        rel = str(entry.get("path") or "")
                        path = bundle_dir / "kernel" / rel
                        if path.is_file():
                            env_parts.append(path.read_bytes())
                digest = hashlib.sha256(b"\n---\n".join(env_parts)).hexdigest()
                actual_env = f"sha256:{digest}"
            else:
                actual_env = compute_lean_environment_hash()
        except (OSError, json.JSONDecodeError, ValueError) as exc:
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

    result.ok = not result.issues
    return result
