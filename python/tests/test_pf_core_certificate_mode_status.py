"""A0 certificate mode status table + public issuance fail-closed policy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.lean_check import resolve_lean_check_artifact_paths, run_pfcore_lean_check
from pcs_core.paths import repo_root
from pcs_core.pf_core_certificate_mode_status import (
    assert_status_table_covers_modes,
    enforce_certificate_mode_issuance,
    get_certificate_mode_status,
    get_external_claim_class_status,
    load_certificate_mode_status,
    public_issuance_modes,
)
from pcs_core.pf_core_lean_codegen import CERTIFICATE_MODES

REPO = repo_root()
FILE_READ = REPO / "examples" / "pf-core-valid" / "file_read_allowed" / "trace.json"
DISABLED_MODES = frozenset(
    {
        "HandoffSafeCertificate",
        "ContractCheckedCertificate",
        "EffectFrameCertificate",
        "FramePreservedCertificate",
    }
)


def test_mode_status_table_loads_and_covers_all_modes() -> None:
    data = load_certificate_mode_status()
    assert data["artifact_type"] == "PFCoreCertificateModeStatus.v0"
    assert_status_table_covers_modes(CERTIFICATE_MODES)
    assert get_certificate_mode_status("TraceSafeRCertificate")["status"] == "release_candidate"
    assert get_certificate_mode_status("TraceSafeCertificate")["status"] == "legacy"
    assert get_certificate_mode_status("CompositionalExtensionCertificate")["status"] == (
        "experimental"
    )
    for mode in DISABLED_MODES:
        entry = get_certificate_mode_status(mode)
        assert entry is not None
        assert entry["status"] == "disabled"
        assert entry["allowed_issuance"] is False
    external = get_external_claim_class_status("CertificateChecked")
    assert external is not None
    assert external["status"] == "preview"


@pytest.mark.parametrize("mode", sorted(DISABLED_MODES))
def test_disabled_modes_fail_closed_on_public_issuance(mode: str) -> None:
    err = enforce_certificate_mode_issuance(mode, release_grade=False)
    assert err is not None
    assert "allowed_issuance=false" in err or "disabled" in err
    err_rg = enforce_certificate_mode_issuance(mode, release_grade=True)
    assert err_rg is not None


def test_experimental_allowed_on_public_cli_but_not_release_grade() -> None:
    mode = "CompositionalExtensionCertificate"
    assert enforce_certificate_mode_issuance(mode, release_grade=False) is None
    err = enforce_certificate_mode_issuance(mode, release_grade=True)
    assert err is not None
    assert "release-grade" in err


def test_public_issuance_modes_sets() -> None:
    public = public_issuance_modes(release_grade=False)
    assert "TraceSafeRCertificate" in public
    assert "TraceSafeCertificate" in public
    assert "CompositionalExtensionCertificate" in public
    assert public.isdisjoint(DISABLED_MODES)
    release = public_issuance_modes(release_grade=True)
    assert "TraceSafeRCertificate" in release
    assert "TraceSafeCertificate" in release
    assert "CompositionalExtensionCertificate" not in release


@pytest.mark.parametrize("mode", sorted(DISABLED_MODES))
def test_lean_check_rejects_disabled_modes_by_default(mode: str, tmp_path: Path) -> None:
    trace = json.loads(FILE_READ.read_text(encoding="utf-8"))
    work = tmp_path / "trace.json"
    work.write_text(json.dumps(trace), encoding="utf-8")
    code, result = run_pfcore_lean_check(
        work,
        certificate_mode=mode,
        skip_build=True,
        skip_lean_proof=True,
        release_grade=False,
    )
    assert code != 0
    codes = [issue.get("code") for issue in result.get("issues", [])]
    assert "CertificateModeIssuanceDenied" in codes


def test_lean_check_reports_deterministic_artifact_paths(tmp_path: Path) -> None:
    out = tmp_path / "PFCoreCertificate.v0.json"
    result_out = tmp_path / "LeanCheckResult.v0.json"
    paths = resolve_lean_check_artifact_paths(
        trace_path=FILE_READ,
        out_path=out,
        result_out_path=result_out,
        generated_proof_path=tmp_path / "proof.lean",
    )
    assert paths["certificate"] == str(out.resolve())
    assert paths["lean_check_result"] == str(result_out.resolve())
    assert paths["generated_proof"] == str((tmp_path / "proof.lean").resolve())
    assert paths["semantic_projection"].endswith("PFCoreSemanticProjection.v0.json")
    assert paths["theorem_manifest"].endswith("PFCoreTheoremManifest.v0.json")

    code, result = run_pfcore_lean_check(
        FILE_READ,
        out_path=out,
        result_out_path=result_out,
        skip_build=True,
        skip_lean_proof=True,
    )
    assert "artifact_paths" in result
    assert result["artifact_paths"]["lean_check_result"] == str(result_out.resolve())
    assert result_out.is_file()
    assert code in (0, 1)


def _workflow_text(name: str) -> str:
    return (REPO / ".github" / "workflows" / name).read_text(encoding="utf-8-sig")


def test_release_workflow_wires_lean_check_result() -> None:
    text = _workflow_text("release.yml")
    assert "workflow_dispatch:" in text
    assert "--result-out /tmp/pfcore-release-lean-check.json" in text
    assert "--lean-check-result /tmp/pfcore-release-lean-check.json" in text
    assert "Upload local release artifacts" in text
    # Preview path still runs lean-check then bundle then validate then attest/absence.
    lean_idx = text.index("--result-out /tmp/pfcore-release-lean-check.json")
    bundle_idx = text.index("--lean-check-result /tmp/pfcore-release-lean-check.json")
    validate_idx = text.index("pcs pf-core validate-bundle ../dist/release-bundle")
    attest_idx = text.index("--allow-absence")
    upload_idx = text.index("Upload local release artifacts")
    assert lean_idx < bundle_idx < validate_idx < attest_idx < upload_idx


def test_pf_core_release_gate_preview_path_includes_lean_check_result() -> None:
    text = _workflow_text("pf-core-release-gate.yml")
    assert "workflow_dispatch:" in text
    assert "--result-out /tmp/pfcore-preview-lean-check.json" in text
    assert "--lean-check-result /tmp/pfcore-preview-lean-check.json" in text
    assert "--result-out /tmp/pfcore-release-lean-check.json" in text
    assert "LEAN_CHECK_RESULT=/tmp/pfcore-release-lean-check.json" in text
    assert '--lean-check-result "${LEAN_CHECK_RESULT}"' in text
    assert "Preview lean-check" in text
    assert "Upload preview release bundle" in text
    preview_lean = text.index("--result-out /tmp/pfcore-preview-lean-check.json")
    preview_bundle = text.index("--lean-check-result /tmp/pfcore-preview-lean-check.json")
    preview_validate = text.index(
        "pcs pf-core validate-bundle /tmp/pfcore-preview-bundle",
        preview_bundle,
    )
    preview_attest = text.index("--allow-absence", preview_validate)
    preview_upload = text.index("Upload preview release bundle")
    assert preview_lean < preview_bundle < preview_validate < preview_attest < preview_upload
