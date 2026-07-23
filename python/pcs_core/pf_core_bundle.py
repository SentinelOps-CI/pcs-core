"""PF-Core release bundle assembly and validation."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from pcs_core.hash import CANONICALIZATION_VERSION, canonical_hash
from pcs_core.lean_check import compute_proof_term_hash, pfcore_generated_dir
from pcs_core.paths import package_dir, repo_root
from pcs_core.pf_core_lean_codegen import (
    compute_lean_environment_hash,
    compute_lean_environment_hash_from_bundle,
    pfcore_kernel_lean_paths,
    resolve_certificate_mode,
)
from pcs_core.pf_core_runtime import compute_trace_hash
from pcs_core.safe_paths import UnsafePathError, resolve_contained_file, strip_repo_generated_prefix
from pcs_core.validate import ValidationError, validate_artifact, validate_schema


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
    elan_pin = repo_root() / "pins" / "elan.json"
    if not elan_pin.is_file():
        bundled_pin = package_dir() / "pins" / "elan.json"
        if bundled_pin.is_file():
            elan_pin = bundled_pin
    if elan_pin.is_file():
        try:
            pin = json.loads(elan_pin.read_text(encoding="utf-8"))
            if isinstance(pin, dict) and pin.get("version"):
                versions["elan"] = str(pin["version"])
            if isinstance(pin, dict) and pin.get("sha256"):
                versions["elan_sha256"] = str(pin["sha256"])
        except (OSError, json.JSONDecodeError):
            pass
    certifyedge_pin = repo_root() / "pins" / "certifyedge.json"
    if not certifyedge_pin.is_file():
        bundled_ce = package_dir() / "pins" / "certifyedge.json"
        if bundled_ce.is_file():
            certifyedge_pin = bundled_ce
    if certifyedge_pin.is_file():
        try:
            pin = json.loads(certifyedge_pin.read_text(encoding="utf-8"))
            if isinstance(pin, dict):
                if pin.get("image_digest"):
                    versions["certifyedge_image_digest"] = str(pin["image_digest"])
                if pin.get("version"):
                    versions["certifyedge"] = str(pin["version"])
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


def build_kernel_manifest() -> dict[str, Any]:
    """Per-file PF-Core kernel manifest for self-contained bundle validation."""
    files: list[dict[str, str]] = []
    for path in pfcore_kernel_lean_paths():
        rel = path.relative_to(repo_root()).as_posix()
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
    repo = repo_root()
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
        src = resolve_contained_file(repo, rel, allowed_suffixes=frozenset({".lean"}))
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
    lean_root = repo_root() / "lean"
    toolchain_src = lean_root / "lean-toolchain"
    if toolchain_src.is_file():
        shutil.copy2(toolchain_src, out_dir / "lean-toolchain")
        dest_toolchain = out_dir / "lean" / "lean-toolchain"
        dest_toolchain.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(toolchain_src, dest_toolchain)
    for rel in ("lakefile.lean", "lake-manifest.json"):
        src = lean_root / rel
        if src.is_file():
            dest = out_dir / "lean" / rel
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
    bundle_dir: Path | None = None,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    trace_hash = str(certificate.get("trace_hash") or trace.get("trace_hash") or "")
    if not trace_hash.startswith("sha256:"):
        trace_hash = compute_trace_hash(dict(trace))
    proof_term_hash = str(certificate.get("proof_term_hash") or "")
    kernel_manifest = kernel_manifest or build_kernel_manifest()
    kernel_root = bundle_dir if bundle_dir is not None else repo_root()
    kernel_files_root = kernel_root / "kernel" if bundle_dir is not None else repo_root()
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
    if proof_rel:
        manifest["proof_path"] = proof_rel
    # LeanKernelChecked requires proof + lean check paths in the closed schema.
    if claim_class == "LeanKernelChecked":
        if not manifest.get("proof_path"):
            raise ValueError("LeanKernelChecked bundle requires proof_path")
        if not manifest.get("lean_check_result_path"):
            raise ValueError("LeanKernelChecked bundle requires lean_check_result_path")
        if not str(manifest.get("proof_term_hash") or "").startswith("sha256:"):
            raise ValueError("LeanKernelChecked bundle requires proof_term_hash")
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

    kernel_manifest = build_kernel_manifest()
    _copy_kernel_into_bundle(out_dir, kernel_manifest)
    _copy_lean_environment_into_bundle(out_dir)

    manifest, _kernel_manifest = build_release_manifest(
        trace=trace,
        certificate=certificate,
        trace_rel=trace_dest.name,
        certificate_rel=cert_dest.name,
        lean_check_result_rel=lean_rel,
        proof_rel=proof_rel,
        kernel_manifest=kernel_manifest,
        trace_path=trace_path,
        bundle_dir=out_dir,
    )
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    kernel_manifest_path = out_dir / "kernel_manifest.json"
    kernel_manifest_path.write_text(json.dumps(kernel_manifest, indent=2) + "\n", encoding="utf-8")
    write_tool_versions(out_dir)
    return manifest_path


def _bundle_resolve(
    bundle_dir: Path,
    rel: str,
    *,
    allowed_suffixes: frozenset[str],
) -> Path:
    return resolve_contained_file(bundle_dir, rel, allowed_suffixes=allowed_suffixes)


def validate_bundle(bundle_dir: Path) -> BundleValidationResult:
    """Validate a PF-Core release bundle directory and manifest hashes.

    Schema validation of the release and kernel manifests runs **before** any
    referenced path is followed.
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
    if lean_check_rel:
        try:
            _bundle_resolve(bundle_root, lean_check_rel, allowed_suffixes=frozenset({".json"}))
        except UnsafePathError as exc:
            result.issues.append(BundleIssue("LeanCheckResultPathUnsafe", str(exc)))

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
        import os

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
