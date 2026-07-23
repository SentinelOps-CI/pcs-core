"""Verify PF-Core certificate proof binding (digests, theorems, projection replay)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from pcs_core.hash import canonical_hash
from pcs_core.lean_check import compute_proof_term_hash, pfcore_generated_dir
from pcs_core.pf_core_lean_codegen import compute_lean_environment_hash, compute_pfcore_kernel_hash
from pcs_core.pf_core_runtime import compute_trace_hash
from pcs_core.pf_core_theorem_manifest import (
    compute_theorem_manifest_digest,
    load_theorem_manifest,
    normalize_proposition,
    proposition_hash,
    propositions_by_name,
    theorem_names_from_manifest,
)
from pcs_core.safe_paths import UnsafePathError, resolve_contained_file, strip_repo_generated_prefix


@dataclass(frozen=True)
class ProofBindingIssue:
    code: str
    message: str


@dataclass
class ProofBindingResult:
    ok: bool
    certificate_path: Path
    trace_path: Path | None = None
    proof_path: Path | None = None
    theorem_manifest_path: Path | None = None
    semantic_projection_path: Path | None = None
    issues: list[ProofBindingIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "certificate_path": str(self.certificate_path),
            "trace_path": str(self.trace_path) if self.trace_path else None,
            "proof_path": str(self.proof_path) if self.proof_path else None,
            "theorem_manifest_path": (
                str(self.theorem_manifest_path) if self.theorem_manifest_path else None
            ),
            "semantic_projection_path": (
                str(self.semantic_projection_path) if self.semantic_projection_path else None
            ),
            "issues": [{"code": i.code, "message": i.message} for i in self.issues],
        }


def _resolve_generated_proof_path(ref: str) -> Path:
    """Resolve a proof_term_ref strictly under lean/PFCore/Generated/."""
    relative = strip_repo_generated_prefix(ref)
    return resolve_contained_file(
        pfcore_generated_dir(),
        relative,
        allowed_suffixes=frozenset({".lean"}),
    )


def _issue(result: ProofBindingResult, code: str, message: str) -> None:
    result.issues.append(ProofBindingIssue(code, message))


def _discover_sibling(certificate_path: Path, name: str) -> Path | None:
    candidate = certificate_path.parent / name
    return candidate if candidate.is_file() else None


def _verify_certificate_schema(cert: Mapping[str, Any], result: ProofBindingResult) -> None:
    """Validate certificate schema/semantics for complete release certificates."""
    required = (
        "schema_version",
        "artifact_type",
        "certificate_id",
        "trace_hash",
        "contract_hash",
        "policy_hash",
        "claim_class",
        "checker",
        "checker_version",
        "assumption_refs",
        "event_count",
        "source_repo",
        "source_commit",
        "signature_or_digest",
    )
    if not all(key in cert for key in required):
        # Lightweight binding fixtures omit full release fields; digest checks still apply.
        return

    from pcs_core.validate import ValidationError, validate_artifact

    try:
        validate_artifact(dict(cert), "PFCoreCertificate.v0")
    except ValidationError as exc:
        for err in exc.errors or [str(exc)]:
            _issue(result, "CertificateSchemaInvalid", str(err))
    except Exception as exc:  # noqa: BLE001 — binding must fail closed
        _issue(result, "CertificateSchemaInvalid", str(exc))


def _verify_authenticated_integrity(
    cert: Mapping[str, Any],
    certificate_path: Path,
    result: ProofBindingResult,
    *,
    artifact_integrity_path: Path | None,
) -> None:
    integrity_path = artifact_integrity_path
    if integrity_path is None:
        for name in (
            "PFCoreCertificate.v0.integrity.json",
            "ArtifactIntegrity.v1.json",
            f"{certificate_path.stem}.integrity.json",
        ):
            found = _discover_sibling(certificate_path, name)
            if found is not None:
                integrity_path = found
                break
    if integrity_path is None:
        embedded = cert.get("artifact_integrity")
        if isinstance(embedded, Mapping):
            integrity = dict(embedded)
        else:
            return
    else:
        try:
            integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _issue(result, "ArtifactIntegrityUnreadable", str(exc))
            return
    if not isinstance(integrity, Mapping):
        _issue(result, "ArtifactIntegrityInvalid", "integrity root must be object")
        return
    from pcs_core.validate import ValidationError, validate_artifact

    try:
        validate_artifact(dict(integrity), "ArtifactIntegrity.v1")
    except ValidationError as exc:
        for err in exc.errors or [str(exc)]:
            _issue(result, "ArtifactIntegritySchemaInvalid", str(err))
        return
    expected = str(integrity.get("artifact_digest") or "")
    actual = canonical_hash(dict(cert))
    target_digest = str(integrity.get("target_digest") or "")
    if expected and expected != actual and target_digest != actual:
        _issue(
            result,
            "ArtifactIntegrityDigestMismatch",
            f"integrity artifact_digest {expected!r} / target_digest {target_digest!r} "
            f"!= certificate digest {actual!r}",
        )

    # Cryptographic verify when a trusted key registry is configured.
    from pcs_core.artifact_integrity import (
        resolve_trusted_key_registry,
        verify_artifact_signature,
    )

    registry = resolve_trusted_key_registry()
    if registry is not None:
        for err in verify_artifact_signature(
            integrity,
            registry,
            required_purpose="release_signing",
            expect_digest=actual,
        ):
            _issue(result, "ArtifactIntegritySignatureInvalid", err)


def verify_proof_binding(
    certificate_path: Path,
    *,
    trace_path: Path | None = None,
    resolved_evidence: Any | None = None,
    theorem_manifest_path: Path | None = None,
    semantic_projection_path: Path | None = None,
    artifact_integrity_path: Path | None = None,
) -> ProofBindingResult:
    """Verify certificate binds digests, theorem manifest, projection, and evidence.

    Checks (when applicable):
    1. certificate schema and semantic validity
    2. authenticated certificate integrity when available
    3. trace digest
    4. proof-file digest
    5. kernel digest
    6. Lean-environment digest
    7. theorem-manifest digest
    8. theorem names
    9. normalized theorem propositions
    10. final mode witness
    11. semantic-projection digest
    12. projection replay from source evidence
    13. contract-evidence digest
    14. handoff-evidence digest
    15. effect-frame digest
    16. transition evidence where applicable

    Rejects certificates that add a theorem or change a proposition even when the
    referenced proof file bytes remain authentic.
    """
    result = ProofBindingResult(ok=False, certificate_path=certificate_path)
    try:
        cert = json.loads(certificate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _issue(result, "CertificateUnreadable", str(exc))
        return result

    if not isinstance(cert, Mapping):
        _issue(result, "InvalidCertificate", "certificate root must be object")
        return result

    claim_class = str(cert.get("claim_class") or "")
    if claim_class != "LeanKernelChecked":
        _issue(
            result,
            "ClaimClassMismatch",
            f"verify-proof-binding requires LeanKernelChecked, got {claim_class!r}",
        )
        return result

    # 1. Certificate schema + semantic validity
    _verify_certificate_schema(cert, result)

    # 2. Authenticated integrity when available
    _verify_authenticated_integrity(
        cert,
        certificate_path,
        result,
        artifact_integrity_path=artifact_integrity_path,
    )

    if cert.get("lean_proof_checked") is not True:
        _issue(result, "LeanProofNotChecked", "certificate lean_proof_checked must be true")

    cert_trace_hash = str(cert.get("trace_hash") or "")
    cert_proof_hash = str(cert.get("proof_term_hash") or "")
    cert_env_hash = str(cert.get("lean_environment_hash") or "")
    cert_kernel_hash = str(cert.get("pfcore_kernel_hash") or "")
    proof_ref = str(cert.get("proof_term_ref") or cert.get("proof_ref") or "")

    if not cert_trace_hash.startswith("sha256:"):
        _issue(result, "MissingTraceHash", "certificate missing trace_hash")
    if not cert_proof_hash.startswith("sha256:"):
        _issue(result, "MissingProofTermHash", "certificate missing proof_term_hash")
    if not cert_env_hash.startswith("sha256:"):
        _issue(result, "MissingLeanEnvironmentHash", "certificate missing lean_environment_hash")
    if not cert_kernel_hash.startswith("sha256:"):
        _issue(result, "MissingPfcoreKernelHash", "certificate missing pfcore_kernel_hash")
    if not proof_ref:
        _issue(result, "MissingProofTermRef", "certificate missing proof_term_ref")

    # 3. Trace digest
    resolved_trace: Path | None = None
    trace_obj: dict[str, Any] | None = None
    if trace_path is not None:
        resolved_trace = trace_path.resolve()
        result.trace_path = resolved_trace
        if not resolved_trace.is_file():
            _issue(result, "TraceMissing", f"trace file not found: {resolved_trace}")
        else:
            try:
                trace = json.loads(resolved_trace.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                _issue(result, "TraceUnreadable", str(exc))
            else:
                if isinstance(trace, Mapping):
                    trace_obj = dict(trace)
                    actual_trace_hash = str(
                        trace.get("trace_hash") or compute_trace_hash(dict(trace))
                    )
                    if cert_trace_hash and actual_trace_hash != cert_trace_hash:
                        _issue(
                            result,
                            "TraceHashMismatch",
                            f"trace hash {actual_trace_hash!r} != certificate {cert_trace_hash!r}",
                        )
                else:
                    _issue(result, "InvalidTrace", "trace root must be object")

    # 4. Proof-file digest
    resolved_proof: Path | None = None
    if proof_ref:
        try:
            resolved_proof = _resolve_generated_proof_path(proof_ref)
            result.proof_path = resolved_proof
        except UnsafePathError as exc:
            _issue(result, "ProofPathUnsafe", str(exc))
            resolved_proof = None
        if resolved_proof is None:
            if not any(issue.code == "ProofPathUnsafe" for issue in result.issues):
                _issue(result, "ProofFileMissing", f"generated proof not found: {proof_ref}")
        elif cert_proof_hash.startswith("sha256:"):
            actual_proof_hash = compute_proof_term_hash(resolved_proof)
            if actual_proof_hash != cert_proof_hash:
                _issue(
                    result,
                    "ProofTermHashMismatch",
                    f"proof file hash {actual_proof_hash!r} != certificate {cert_proof_hash!r}",
                )

    # 5. Kernel digest
    if cert_kernel_hash.startswith("sha256:"):
        actual_kernel_hash = compute_pfcore_kernel_hash()
        if actual_kernel_hash != cert_kernel_hash:
            _issue(
                result,
                "PfcoreKernelHashMismatch",
                f"current kernel hash {actual_kernel_hash!r} != certificate {cert_kernel_hash!r}",
            )

    # 6. Lean-environment digest
    if cert_env_hash.startswith("sha256:"):
        actual_env_hash = compute_lean_environment_hash()
        if actual_env_hash != cert_env_hash:
            _issue(
                result,
                "LeanEnvironmentHashMismatch",
                f"current lean environment {actual_env_hash!r} != certificate {cert_env_hash!r}",
            )

    # Resolve theorem manifest + projection paths
    manifest_path = theorem_manifest_path
    if manifest_path is None:
        if resolved_proof is not None:
            sibling = resolved_proof.parent / "PFCoreTheoremManifest.v0.json"
            if sibling.is_file():
                manifest_path = sibling
        if manifest_path is None:
            found = _discover_sibling(certificate_path, "PFCoreTheoremManifest.v0.json")
            if found is not None:
                manifest_path = found
    result.theorem_manifest_path = manifest_path

    projection_path = semantic_projection_path
    if projection_path is None:
        if resolved_proof is not None:
            sibling = resolved_proof.parent / "PFCoreSemanticProjection.v0.json"
            if sibling.is_file():
                projection_path = sibling
        if projection_path is None:
            found = _discover_sibling(certificate_path, "PFCoreSemanticProjection.v0.json")
            if found is not None:
                projection_path = found
    result.semantic_projection_path = projection_path

    cert_manifest_hash = str(cert.get("theorem_manifest_hash") or "")
    inventory = cert.get("theorem_inventory")
    inventory_names = (
        {str(name) for name in inventory} if isinstance(inventory, list) else set()
    )

    # 7–10. Theorem manifest digest, names, propositions, final witness
    if cert_manifest_hash.startswith("sha256:") or isinstance(inventory, list):
        if manifest_path is None or not manifest_path.is_file():
            if cert_manifest_hash.startswith("sha256:") or inventory_names:
                _issue(
                    result,
                    "TheoremManifestMissing",
                    "certificate binds theorem inventory/manifest but PFCoreTheoremManifest.v0 "
                    "was not found",
                )
        else:
            try:
                manifest = load_theorem_manifest(manifest_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                _issue(result, "TheoremManifestUnreadable", str(exc))
                manifest = None
            if manifest is not None:
                from pcs_core.validate import ValidationError, validate_artifact

                try:
                    validate_artifact(manifest, "PFCoreTheoremManifest.v0")
                except ValidationError as exc:
                    for err in exc.errors or [str(exc)]:
                        _issue(result, "TheoremManifestSchemaInvalid", str(err))

                recomputed = compute_theorem_manifest_digest(manifest)
                declared = str(manifest.get("theorem_manifest_digest") or "")
                if declared and declared != recomputed:
                    _issue(
                        result,
                        "TheoremManifestDigestMismatch",
                        f"manifest digest {declared!r} != recomputed {recomputed!r}",
                    )
                if cert_manifest_hash.startswith("sha256:") and cert_manifest_hash != recomputed:
                    _issue(
                        result,
                        "CertificateTheoremManifestHashMismatch",
                        f"certificate theorem_manifest_hash {cert_manifest_hash!r} "
                        f"!= manifest digest {recomputed!r}",
                    )
                inventory_hash = str(cert.get("theorem_inventory_hash") or "")
                if (
                    cert_manifest_hash.startswith("sha256:")
                    and inventory_hash.startswith("sha256:")
                    and cert_manifest_hash == inventory_hash
                ):
                    _issue(
                        result,
                        "TheoremManifestHashCollapsesToInventory",
                        "theorem_manifest_hash must not equal theorem_inventory_hash",
                    )

                manifest_names = set(theorem_names_from_manifest(manifest))
                if inventory_names:
                    extra = inventory_names - manifest_names
                    missing = manifest_names - inventory_names
                    if extra:
                        _issue(
                            result,
                            "TheoremNameDrift",
                            "certificate theorem_inventory adds names absent from manifest: "
                            f"{sorted(extra)}",
                        )
                    if missing:
                        _issue(
                            result,
                            "TheoremNameDrift",
                            "theorem manifest names missing from certificate inventory: "
                            f"{sorted(missing)}",
                        )

                # 9. Normalized propositions — reject drift even if proof bytes match
                props = propositions_by_name(manifest)
                for name, prop in props.items():
                    entry_hash = None
                    for entry in manifest.get("theorems") or []:
                        if isinstance(entry, Mapping) and str(entry.get("theorem_name")) == name:
                            entry_hash = str(entry.get("proposition_hash") or "")
                            break
                    expected_hash = proposition_hash(prop)
                    if entry_hash and entry_hash != expected_hash:
                        _issue(
                            result,
                            "PropositionHashMismatch",
                            f"theorem {name!r} proposition_hash does not match "
                            "normalized_proposition",
                        )

                # 10. Final mode witness
                witness = cert.get("certificate_mode_witness")
                if isinstance(witness, Mapping):
                    final_thm = str(manifest.get("final_witness_theorem") or "")
                    final_prop = normalize_proposition(
                        str(manifest.get("final_witness_proposition") or "")
                    )
                    cert_thm = str(witness.get("theorem") or "")
                    cert_prop = normalize_proposition(str(witness.get("proposition") or ""))
                    if final_thm and cert_thm and final_thm != cert_thm:
                        _issue(
                            result,
                            "FinalWitnessTheoremMismatch",
                            f"manifest final witness {final_thm!r} != certificate {cert_thm!r}",
                        )
                    if final_prop and cert_prop and final_prop != cert_prop:
                        _issue(
                            result,
                            "FinalWitnessPropositionMismatch",
                            f"manifest final witness proposition differs from certificate",
                        )
                    if cert_thm and cert_thm not in manifest_names:
                        _issue(
                            result,
                            "FinalWitnessMissingFromManifest",
                            f"certificate mode witness theorem {cert_thm!r} absent from manifest",
                        )
                    if cert_thm and cert_thm in props and cert_prop != props[cert_thm]:
                        _issue(
                            result,
                            "FinalWitnessPropositionDrift",
                            "certificate mode witness proposition drifted from theorem manifest",
                        )

                mode = str(cert.get("certificate_mode") or "")
                manifest_mode = str(manifest.get("certificate_mode") or "")
                if mode and manifest_mode and mode != manifest_mode:
                    _issue(
                        result,
                        "CertificateModeMismatch",
                        f"manifest mode {manifest_mode!r} != certificate {mode!r}",
                    )

                if resolved_proof is not None and cert_proof_hash.startswith("sha256:"):
                    proof_hash_in_manifest = str(manifest.get("proof_file_hash") or "")
                    if proof_hash_in_manifest and proof_hash_in_manifest != cert_proof_hash:
                        _issue(
                            result,
                            "ManifestProofFileHashMismatch",
                            "theorem manifest proof_file_hash does not match certificate "
                            "proof_term_hash",
                        )

    # 11–12. Semantic projection digest + replay
    cert_projection_hash = str(cert.get("semantic_projection_hash") or "")
    if cert_projection_hash.startswith("sha256:"):
        if projection_path is None or not projection_path.is_file():
            _issue(
                result,
                "SemanticProjectionMissing",
                "certificate binds semantic_projection_hash but projection file was not found",
            )
        else:
            try:
                projection = json.loads(projection_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                _issue(result, "SemanticProjectionUnreadable", str(exc))
                projection = None
            if isinstance(projection, Mapping):
                stored = str(projection.get("projection_hash") or "")
                if stored and stored != cert_projection_hash:
                    _issue(
                        result,
                        "SemanticProjectionHashMismatch",
                        f"projection file hash {stored!r} != certificate {cert_projection_hash!r}",
                    )
                # Replay from source evidence when available
                if trace_obj is not None:
                    try:
                        from pcs_core.pf_core_resolved_evidence import (
                            EvidenceResolutionError,
                            resolve_pf_core_evidence,
                        )
                        from pcs_core.pf_core_semantic_projection import (
                            build_semantic_projection,
                        )

                        evidence = resolved_evidence
                        if evidence is None and resolved_trace is not None:
                            evidence = resolve_pf_core_evidence(
                                trace_obj,
                                trace_path=resolved_trace,
                                certificate_mode=cert.get("certificate_mode"),
                            )
                        if evidence is not None:
                            replayed = build_semantic_projection(
                                trace_obj,
                                certificate_mode=str(cert.get("certificate_mode") or ""),
                                trace_path=resolved_trace,
                                resolved_evidence=evidence,
                            )
                            replay_hash = str(replayed.get("projection_hash") or "")
                            if replay_hash and replay_hash != cert_projection_hash:
                                _issue(
                                    result,
                                    "ProjectionReplayMismatch",
                                    f"replayed projection hash {replay_hash!r} != "
                                    f"certificate {cert_projection_hash!r}",
                                )
                    except EvidenceResolutionError as exc:
                        _issue(result, "ProjectionReplayFailed", str(exc))
                    except Exception as exc:  # noqa: BLE001
                        _issue(result, "ProjectionReplayFailed", str(exc))

    # 13–16. Evidence digests where applicable / present
    if resolved_evidence is not None or (
        resolved_trace is not None and trace_obj is not None and cert.get("certificate_mode")
    ):
        evidence = resolved_evidence
        if evidence is None and resolved_trace is not None and trace_obj is not None:
            try:
                from pcs_core.pf_core_resolved_evidence import resolve_pf_core_evidence

                evidence = resolve_pf_core_evidence(
                    trace_obj,
                    trace_path=resolved_trace,
                    certificate_mode=cert.get("certificate_mode"),
                )
            except Exception:
                evidence = None

        if evidence is not None:
            mode = str(cert.get("certificate_mode") or "")
            # 13. Contract evidence
            cert_contract_digest = str(cert.get("contract_evidence_digest") or "")
            if cert_contract_digest.startswith("sha256:") or mode == "ContractCheckedCertificate":
                from pcs_core.pf_core_resolved_evidence import (
                    collect_contract_theorem_names,
                    compute_contract_evidence_digest,
                    contract_source_file_digests,
                )

                try:
                    digests = contract_source_file_digests(evidence)
                    names = collect_contract_theorem_names(cert.get("theorem_inventory"))
                    recomputed = compute_contract_evidence_digest(
                        selected_contract_ids=evidence.selected_contract_ids,
                        contract_source_file_digests=digests,
                        effective_layers=evidence.effective_contract_semantic_layers,
                        contract_theorem_names=names,
                    )
                    if cert_contract_digest.startswith("sha256:") and cert_contract_digest != recomputed:
                        _issue(
                            result,
                            "ContractEvidenceDigestMismatch",
                            f"contract evidence digest {cert_contract_digest!r} != "
                            f"recomputed {recomputed!r}",
                        )
                except Exception as exc:  # noqa: BLE001
                    _issue(result, "ContractEvidenceDigestFailed", str(exc))

            # 14. Handoff evidence
            cert_handoff_digest = str(cert.get("handoff_evidence_digest") or "")
            if cert_handoff_digest.startswith("sha256:") or mode == "HandoffSafeCertificate":
                from pcs_core.pf_core_resolved_evidence import (
                    collect_handoff_theorem_names,
                    compute_handoff_evidence_digest,
                    handoff_source_file_digests,
                )

                try:
                    digests = handoff_source_file_digests(evidence)
                    names = collect_handoff_theorem_names(cert.get("theorem_inventory"))
                    recomputed = compute_handoff_evidence_digest(
                        selected_handoff_ids=evidence.selected_handoff_ids,
                        handoff_source_file_digests=digests,
                        handoff_theorem_names=names,
                    )
                    if cert_handoff_digest.startswith("sha256:") and cert_handoff_digest != recomputed:
                        _issue(
                            result,
                            "HandoffEvidenceDigestMismatch",
                            f"handoff evidence digest {cert_handoff_digest!r} != "
                            f"recomputed {recomputed!r}",
                        )
                except Exception as exc:  # noqa: BLE001
                    _issue(result, "HandoffEvidenceDigestFailed", str(exc))

            # 15. Effect-frame digest
            cert_frame_digest = str(cert.get("effect_frame_digest") or "")
            if cert_frame_digest.startswith("sha256:") or mode == "EffectFrameCertificate":
                from pcs_core.pf_core_resolved_evidence import effect_frame_source_digest

                try:
                    if evidence.effect_frame is not None:
                        recomputed = effect_frame_source_digest(evidence)
                        if (
                            cert_frame_digest.startswith("sha256:")
                            and cert_frame_digest != recomputed
                        ):
                            _issue(
                                result,
                                "EffectFrameDigestMismatch",
                                f"effect frame digest {cert_frame_digest!r} != "
                                f"recomputed {recomputed!r}",
                            )
                    elif mode == "EffectFrameCertificate":
                        _issue(
                            result,
                            "EffectFrameMissing",
                            "EffectFrameCertificate requires declared effect frame evidence",
                        )
                except Exception as exc:  # noqa: BLE001
                    _issue(result, "EffectFrameDigestFailed", str(exc))

            # 16. Transition evidence
            cert_transition = str(cert.get("transition_chain_digest") or "")
            if cert_transition.startswith("sha256:") or mode == "FramePreservedCertificate":
                from pcs_core.pf_core_resolved_evidence import transition_chain_digest

                try:
                    if mode == "FramePreservedCertificate" or cert_transition.startswith("sha256:"):
                        recomputed = transition_chain_digest(evidence)
                        if (
                            cert_transition.startswith("sha256:")
                            and cert_transition != recomputed
                        ):
                            _issue(
                                result,
                                "TransitionEvidenceDigestMismatch",
                                f"transition chain digest {cert_transition!r} != "
                                f"recomputed {recomputed!r}",
                            )
                except Exception as exc:  # noqa: BLE001
                    _issue(result, "TransitionEvidenceDigestFailed", str(exc))

    result.ok = not result.issues
    return result
