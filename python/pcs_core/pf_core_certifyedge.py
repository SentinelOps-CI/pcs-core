"""CertifyEdge external checker integration for PF-Core traces."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pcs_core.pf_core_certificate import attach_external_certificate_check
from pcs_core.validate import validate_schema

CERTIFYEDGE_INSTALL_DOC = (
    "Install CertifyEdge from https://github.com/fraware/CertifyEdge and ensure "
    "the `certifyedge` CLI is on PATH, or set PCS_CERTIFYEDGE_MOCK=1 for CI/demo."
)


@dataclass(frozen=True)
class CertificateCheckResult:
    ok: bool
    checker: str
    checker_version: str
    property_id: str
    external_status: str
    message: str
    attestation_ref: str | None = None
    mock: bool = False
    certificate: dict[str, Any] | None = None


def certifyedge_mock_enabled() -> bool:
    return os.environ.get("PCS_CERTIFYEDGE_MOCK", "").strip() in {"1", "true", "yes"}


def _find_certifyedge_cli() -> str | None:
    return shutil.which("certifyedge")


def _load_trace(trace_path: Path) -> dict[str, Any]:
    data = json.loads(trace_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{trace_path}: trace root must be a JSON object")
    return data


def run_certifyedge_check(
    trace_path: Path | str,
    property_spec: str,
    *,
    checker_version: str = "0.1.0",
    attestation_ref: str | None = None,
) -> CertificateCheckResult:
    """Run CertifyEdge (or mock) against a PFCoreTrace and return check metadata."""
    path = Path(trace_path)
    trace = _load_trace(path)
    property_id = property_spec.strip()
    if not property_id:
        raise ValueError("property_spec (property id) is required")

    if certifyedge_mock_enabled():
        mock_ref = attestation_ref or f"mock://certifyedge/{property_id}"
        cert = attach_external_certificate_check(
            trace,
            checker="certifyedge",
            checker_version=checker_version,
            external_status="CertificateChecked",
            attestation_ref=mock_ref,
        )
        cert["obligations"] = [
            {
                "kind": "ExternalCheckerAttestation",
                "theorem": "external_checker_attestation",
                "passed": True,
                "proof_ref": mock_ref,
            },
            {
                "kind": "CertifyEdgePropertyCheck",
                "theorem": "certifyedge_property_check",
                "passed": True,
                "proof_ref": property_id,
            },
        ]
        return CertificateCheckResult(
            ok=True,
            checker="certifyedge",
            checker_version=checker_version,
            property_id=property_id,
            external_status="CertificateChecked",
            message="CertifyEdge mock attestation (PCS_CERTIFYEDGE_MOCK=1)",
            attestation_ref=mock_ref,
            mock=True,
            certificate=cert,
        )

    cli = _find_certifyedge_cli()
    if cli is None:
        return CertificateCheckResult(
            ok=False,
            checker="certifyedge",
            checker_version=checker_version,
            property_id=property_id,
            external_status="Rejected",
            message=f"CertifyEdge CLI not found. {CERTIFYEDGE_INSTALL_DOC}",
        )

    cmd = [
        cli,
        "check-trace",
        "--trace",
        str(path),
        "--property",
        property_id,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        return CertificateCheckResult(
            ok=False,
            checker="certifyedge",
            checker_version=checker_version,
            property_id=property_id,
            external_status="Rejected",
            message=f"CertifyEdge invocation failed: {exc}. {CERTIFYEDGE_INSTALL_DOC}",
        )

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return CertificateCheckResult(
            ok=False,
            checker="certifyedge",
            checker_version=checker_version,
            property_id=property_id,
            external_status="Rejected",
            message=detail or "CertifyEdge check-trace failed",
        )

    resolved_ref = attestation_ref or detail_attestation_ref(proc.stdout)
    cert = attach_external_certificate_check(
        trace,
        checker="certifyedge",
        checker_version=checker_version,
        external_status="CertificateChecked",
        attestation_ref=resolved_ref,
    )
    cert["obligations"] = [
        {
            "kind": "ExternalCheckerAttestation",
            "theorem": "external_checker_attestation",
            "passed": True,
            "proof_ref": resolved_ref,
        },
        {
            "kind": "CertifyEdgePropertyCheck",
            "theorem": "certifyedge_property_check",
            "passed": True,
            "proof_ref": property_id,
        },
    ]
    return CertificateCheckResult(
        ok=True,
        checker="certifyedge",
        checker_version=checker_version,
        property_id=property_id,
        external_status="CertificateChecked",
        message="CertifyEdge check-trace succeeded",
        attestation_ref=resolved_ref,
        mock=False,
        certificate=cert,
    )


def detail_attestation_ref(stdout: str) -> str | None:
    """Best-effort parse of CertifyEdge stdout for an attestation path."""
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("attestation:"):
            return stripped.split(":", 1)[1].strip()
    return None


def write_certifyedge_certificate(
    trace_path: Path | str,
    property_spec: str,
    out_path: Path,
    *,
    checker_version: str = "0.1.0",
    attestation_ref: str | None = None,
) -> CertificateCheckResult:
    result = run_certifyedge_check(
        trace_path,
        property_spec,
        checker_version=checker_version,
        attestation_ref=attestation_ref,
    )
    if not result.ok or result.certificate is None:
        raise RuntimeError(result.message)
    cert = result.certificate
    if cert.get("claim_class") != "CertificateChecked":
        raise RuntimeError("CertifyEdge path must emit CertificateChecked only")
    errors = validate_schema(cert, "PFCoreCertificate.v0")
    if errors:
        raise RuntimeError(f"invalid PFCoreCertificate.v0: {'; '.join(errors)}")
    out_path.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
    return result
