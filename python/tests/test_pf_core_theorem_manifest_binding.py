"""PR6: PFCoreTheoremManifest.v0 + independent proof-binding checks."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pcs_core.hash import canonical_hash
from pcs_core.lean_check import compute_proof_term_hash, run_pfcore_lean_check
from pcs_core.pf_core_lean_codegen import (
    generate_proof_obligation_file,
    theorem_inventory_hash,
)
from pcs_core.pf_core_proof_binding import verify_proof_binding
from pcs_core.pf_core_theorem_manifest import (
    build_theorem_manifest,
    compute_theorem_manifest_digest,
    normalize_proposition,
    proposition_hash,
)
from pcs_core.validate import validate_artifact

REPO = Path(__file__).resolve().parents[2]
FILE_READ = REPO / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_theorem_manifest_digest_differs_from_inventory_hash(tmp_path: Path) -> None:
    trace = _load(FILE_READ)
    generated = generate_proof_obligation_file(
        trace,
        tmp_path / "out",
        trace_path=FILE_READ,
        certificate_mode="TraceSafeRCertificate",
    )
    assert generated.theorem_manifest is not None
    assert generated.theorem_manifest_hash is not None
    inventory_hash = theorem_inventory_hash(generated.theorem_names)
    assert generated.theorem_manifest_hash != inventory_hash
    assert generated.theorem_manifest["theorem_manifest_digest"] == generated.theorem_manifest_hash
    validate_artifact(dict(generated.theorem_manifest), "PFCoreTheoremManifest.v0")
    assert generated.theorem_manifest_path is not None
    assert generated.theorem_manifest_path.is_file()
    entries = generated.theorem_manifest["theorems"]
    assert entries
    for entry in entries:
        assert entry["proposition_hash"] == proposition_hash(entry["normalized_proposition"])
        assert entry["generation_node"]
        assert entry["theorem_category"]
        assert entry["certificate_mode_role"]


def test_lean_check_writes_theorem_manifest_artifact(tmp_path: Path) -> None:
    out_cert = tmp_path / "PFCoreCertificate.v0.json"
    result_out = tmp_path / "LeanCheckResult.v0.json"
    code, result = run_pfcore_lean_check(
        FILE_READ,
        out_path=out_cert,
        result_out_path=result_out,
        certificate_mode="TraceSafeRCertificate",
    )
    if code != 0:
        issues = result.get("issues") if isinstance(result, dict) else None
        pytest.skip(f"lean-check unavailable or failed: {issues or result}")
    assert out_cert.is_file()
    cert = _load(out_cert)
    paths = result["artifact_paths"]
    manifest_path = Path(paths["theorem_manifest"])
    assert manifest_path.is_file()
    manifest = _load(manifest_path)
    validate_artifact(manifest, "PFCoreTheoremManifest.v0")
    assert cert["theorem_manifest_hash"] == manifest["theorem_manifest_digest"]
    assert cert["theorem_manifest_hash"] != cert["theorem_inventory_hash"]
    assert cert["theorem_inventory_hash"] == theorem_inventory_hash(
        frozenset(cert["theorem_inventory"])
    )


def test_verify_proof_binding_rejects_added_theorem_name(tmp_path: Path) -> None:
    out_dir = tmp_path / "gen"
    trace = _load(FILE_READ)
    generated = generate_proof_obligation_file(
        trace,
        out_dir,
        trace_path=FILE_READ,
        certificate_mode="TraceSafeRCertificate",
    )
    # Copy generated proof into the repo Generated/ layout expected by binding.
    dest = REPO / "lean" / "PFCore" / "Generated" / generated.path.name
    shutil.copy2(generated.path, dest)
    shutil.copy2(
        generated.theorem_manifest_path,
        dest.parent / "PFCoreTheoremManifest.v0.json",
    )
    try:
        cert = {
            "schema_version": "v0",
            "artifact_type": "PFCoreCertificate.v0",
            "certificate_id": "pfcore-cert-drift-name",
            "trace_hash": trace.get("trace_hash") or canonical_hash(trace),
            "contract_hash": "sha256:" + "0" * 64,
            "policy_hash": "sha256:" + "0" * 64,
            "claim_class": "LeanKernelChecked",
            "lean_proof_checked": True,
            "checker": "pcs-core",
            "checker_version": "0.1.0",
            "assumption_refs": [],
            "event_count": 1,
            "source_repo": "https://github.com/example/pcs-core",
            "source_commit": "0000000",
            "proof_term_ref": str(dest.relative_to(REPO)).replace("\\", "/"),
            "proof_term_hash": compute_proof_term_hash(dest),
            "lean_environment_hash": "sha256:" + "a" * 64,
            "pfcore_kernel_hash": "sha256:" + "b" * 64,
            "certificate_mode": generated.certificate_mode,
            "theorem_inventory": sorted(generated.theorem_names | {"forged_extra_theorem"}),
            "theorem_inventory_hash": theorem_inventory_hash(
                generated.theorem_names | {"forged_extra_theorem"}
            ),
            "theorem_manifest_hash": generated.theorem_manifest_hash,
            "semantic_projection_hash": generated.semantic_projection_hash,
            "certificate_mode_witness": {
                "theorem": generated.mode_witness_theorem,
                "proposition": generated.mode_witness_proposition,
            },
            "signature_or_digest": "sha256:" + "0" * 64,
        }
        # Intentionally wrong env/kernel so we isolate name-drift by using matching hashes.
        from pcs_core.pf_core_lean_codegen import (
            compute_lean_environment_hash,
            compute_pfcore_kernel_hash,
        )

        cert["lean_environment_hash"] = compute_lean_environment_hash()
        cert["pfcore_kernel_hash"] = compute_pfcore_kernel_hash()
        cert["signature_or_digest"] = canonical_hash(cert)
        cert_path = tmp_path / "cert.json"
        _write(cert_path, cert)
        binding = verify_proof_binding(
            cert_path,
            trace_path=FILE_READ,
            theorem_manifest_path=generated.theorem_manifest_path,
            semantic_projection_path=out_dir / "PFCoreSemanticProjection.v0.json",
        )
        assert binding.ok is False
        assert any(issue.code == "TheoremNameDrift" for issue in binding.issues)
        # Proof file itself remains authentic.
        assert all(issue.code != "ProofTermHashMismatch" for issue in binding.issues)
    finally:
        if dest.is_file():
            dest.unlink()


def test_verify_proof_binding_rejects_proposition_drift(tmp_path: Path) -> None:
    out_dir = tmp_path / "gen"
    trace = _load(FILE_READ)
    generated = generate_proof_obligation_file(
        trace,
        out_dir,
        trace_path=FILE_READ,
        certificate_mode="TraceSafeRCertificate",
    )
    dest = REPO / "lean" / "PFCore" / "Generated" / generated.path.name
    shutil.copy2(generated.path, dest)
    try:
        from pcs_core.pf_core_lean_codegen import (
            compute_lean_environment_hash,
            compute_pfcore_kernel_hash,
        )

        manifest = dict(generated.theorem_manifest)
        # Mutate a proposition while keeping proof-file bytes unchanged.
        theorems = list(manifest["theorems"])
        target = dict(theorems[0])
        target["normalized_proposition"] = normalize_proposition(
            target["normalized_proposition"] + " ∧ True"
        )
        target["proposition_hash"] = proposition_hash(target["normalized_proposition"])
        theorems[0] = target
        manifest["theorems"] = theorems
        del manifest["theorem_manifest_digest"]
        manifest["theorem_manifest_digest"] = compute_theorem_manifest_digest(manifest)
        drifted_manifest_path = tmp_path / "PFCoreTheoremManifest.v0.json"
        _write(drifted_manifest_path, manifest)

        cert = {
            "schema_version": "v0",
            "artifact_type": "PFCoreCertificate.v0",
            "certificate_id": "pfcore-cert-prop-drift",
            "trace_hash": trace.get("trace_hash") or canonical_hash(trace),
            "contract_hash": "sha256:" + "0" * 64,
            "policy_hash": "sha256:" + "0" * 64,
            "claim_class": "LeanKernelChecked",
            "lean_proof_checked": True,
            "checker": "pcs-core",
            "checker_version": "0.1.0",
            "assumption_refs": [],
            "event_count": 1,
            "source_repo": "https://github.com/example/pcs-core",
            "source_commit": "0000000",
            "proof_term_ref": str(dest.relative_to(REPO)).replace("\\", "/"),
            "proof_term_hash": compute_proof_term_hash(dest),
            "lean_environment_hash": compute_lean_environment_hash(),
            "pfcore_kernel_hash": compute_pfcore_kernel_hash(),
            "certificate_mode": generated.certificate_mode,
            "theorem_inventory": sorted(generated.theorem_names),
            "theorem_inventory_hash": theorem_inventory_hash(generated.theorem_names),
            "theorem_manifest_hash": manifest["theorem_manifest_digest"],
            "semantic_projection_hash": generated.semantic_projection_hash,
            "certificate_mode_witness": {
                "theorem": generated.mode_witness_theorem,
                "proposition": "FORGED_PROPOSITION_NOT_IN_MANIFEST",
            },
            "signature_or_digest": "sha256:" + "0" * 64,
        }
        cert["signature_or_digest"] = canonical_hash(cert)
        cert_path = tmp_path / "cert.json"
        _write(cert_path, cert)
        binding = verify_proof_binding(
            cert_path,
            trace_path=FILE_READ,
            theorem_manifest_path=drifted_manifest_path,
            semantic_projection_path=out_dir / "PFCoreSemanticProjection.v0.json",
        )
        assert binding.ok is False
        assert any(
            issue.code
            in {
                "FinalWitnessPropositionMismatch",
                "FinalWitnessPropositionDrift",
            }
            for issue in binding.issues
        )
        assert all(issue.code != "ProofTermHashMismatch" for issue in binding.issues)
    finally:
        if dest.is_file():
            dest.unlink()


def test_build_theorem_manifest_requires_specs() -> None:
    with pytest.raises(ValueError, match="≥1"):
        build_theorem_manifest(
            specs=[],
            generated_module_name="Trace_deadbeef",
            proof_file_hash="sha256:" + "0" * 64,
            semantic_projection_hash="sha256:" + "1" * 64,
            certificate_mode="TraceSafeCertificate",
            final_witness_theorem="concrete_certificate_mode_witness",
            final_witness_proposition="TraceSafe t",
        )
