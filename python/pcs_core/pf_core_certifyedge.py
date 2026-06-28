"""CertifyEdge external checker integration for PF-Core traces."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pcs_core.pf_core_certificate import attach_external_certificate_check
from pcs_core.validate import validate_schema

CertifyEdgeMode = Literal["auto", "live", "mock"]

CERTIFYEDGE_INSTALL_DOC = (
    "Install CertifyEdge from https://github.com/fraware/CertifyEdge and ensure "
    "the `certifyedge` CLI is on PATH, set PF_CORE_CERTIFYEDGE_CLI to the binary path, "
    "or set PF_CORE_CERTIFYEDGE_MODE=mock (or PF_CORE_CERTIFYEDGE_MOCK=1) for CI/demo."
)

# Backward-compatible alias retained for existing CI scripts.
_LEGACY_MOCK_ENV = "PCS_CERTIFYEDGE_MOCK"


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


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def certifyedge_require_live() -> bool:
    """When true, missing live CLI is a hard failure (release gate / ``--require-live``)."""
    return _truthy_env("PF_CORE_CERTIFYEDGE_REQUIRE_LIVE")


def certifyedge_mode() -> CertifyEdgeMode:
    """Resolved CertifyEdge execution mode from ``PF_CORE_CERTIFYEDGE_*`` env vars."""
    raw = os.environ.get("PF_CORE_CERTIFYEDGE_MODE", "").strip().lower()
    if raw in {"mock", "live", "auto"}:
        return raw
    if _truthy_env("PF_CORE_CERTIFYEDGE_MOCK") or _truthy_env(_LEGACY_MOCK_ENV):
        return "mock"
    return "auto"


def certifyedge_mock_enabled() -> bool:
    return certifyedge_mode() == "mock"


def certifyedge_cli_available() -> bool:
    return _find_certifyedge_cli() is not None


def certifyedge_status() -> dict[str, object]:
    """Report CertifyEdge CLI availability for operators and CI."""
    mode = certifyedge_mode()
    cli = _find_certifyedge_cli()
    return {
        "available": cli is not None,
        "cli_path": cli,
        "mode": mode,
        "mock_enabled": mode == "mock",
        "live_required": mode == "live" or certifyedge_require_live(),
        "require_live_env": certifyedge_require_live(),
        "env_contract": {
            "PF_CORE_CERTIFYEDGE_MODE": "auto | live | mock (default: auto)",
            "PF_CORE_CERTIFYEDGE_CLI": "optional explicit path to certifyedge binary",
            "PF_CORE_CERTIFYEDGE_MOCK": "1 forces mock mode (alias: PCS_CERTIFYEDGE_MOCK)",
            "PF_CORE_CERTIFYEDGE_REQUIRE_LIVE": "1 fails when live CLI absent (release gate)",
        },
        "install_doc": CERTIFYEDGE_INSTALL_DOC,
    }


def _find_certifyedge_cli() -> str | None:
    explicit = os.environ.get("PF_CORE_CERTIFYEDGE_CLI", "").strip()
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return str(path)
        resolved = shutil.which(explicit)
        if resolved:
            return resolved
    return shutil.which("certifyedge")


def _certifyedge_cmd(cli: str) -> list[str]:
    """Build argv for CertifyEdge invocation (supports ``.py`` stub scripts)."""
    import sys

    path = Path(cli)
    if path.suffix == ".py" and path.is_file():
        return [sys.executable, str(path)]
    return [cli]


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
    require_live: bool = False,
) -> CertificateCheckResult:
    """Run CertifyEdge (live or mock) against a PFCoreTrace and return check metadata."""
    import sys

    path = Path(trace_path)
    trace = _load_trace(path)
    property_id = property_spec.strip()
    if not property_id:
        raise ValueError("property_spec (property id) is required")

    mode = certifyedge_mode()
    require_live = require_live or certifyedge_require_live()

    if mode == "mock":
        print(
            "WARNING: CertifyEdge mock mode (PF_CORE_CERTIFYEDGE_MODE=mock or "
            "PF_CORE_CERTIFYEDGE_MOCK=1) — not a live external attestation. "
            "Install CertifyEdge and use PF_CORE_CERTIFYEDGE_MODE=live for production.",
            file=sys.stderr,
        )
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
            message="CertifyEdge mock attestation (PF_CORE_CERTIFYEDGE_MODE=mock)",
            attestation_ref=mock_ref,
            mock=True,
            certificate=cert,
        )

    cli = _find_certifyedge_cli()
    if cli is None:
        if mode == "auto" and not require_live:
            print(
                "WARNING: CertifyEdge CLI not found on PATH; failing closed. "
                f"{CERTIFYEDGE_INSTALL_DOC}",
                file=sys.stderr,
            )
            return CertificateCheckResult(
                ok=False,
                checker="certifyedge",
                checker_version=checker_version,
                property_id=property_id,
                external_status="Rejected",
                message=f"CertifyEdge CLI not found. {CERTIFYEDGE_INSTALL_DOC}",
            )
        return CertificateCheckResult(
            ok=False,
            checker="certifyedge",
            checker_version=checker_version,
            property_id=property_id,
            external_status="Rejected",
            message=(
                f"PF_CORE_CERTIFYEDGE_MODE=live or --require-live requires CertifyEdge CLI. "
                f"{CERTIFYEDGE_INSTALL_DOC}"
            ),
        )

    cmd = _certifyedge_cmd(cli) + [
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
        message="CertifyEdge check-trace succeeded (live)",
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
    require_live: bool = False,
) -> CertificateCheckResult:
    result = run_certifyedge_check(
        trace_path,
        property_spec,
        checker_version=checker_version,
        attestation_ref=attestation_ref,
        require_live=require_live,
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
