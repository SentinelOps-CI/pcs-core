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
AttestationClass = Literal["live", "stub", "mock"]

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
    attestation_class: AttestationClass | None = None
    mock: bool = False
    certificate: dict[str, Any] | None = None


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def certifyedge_allow_stub() -> bool:
    """When true, format-validation stub may satisfy ``require_live`` (local/staging only)."""
    return _truthy_env("PF_CORE_CERTIFYEDGE_ALLOW_STUB")


def certifyedge_require_live() -> bool:
    """When true, missing live CLI is a hard failure (release gate / ``--require-live``)."""
    return _truthy_env("PF_CORE_CERTIFYEDGE_REQUIRE_LIVE")


def classify_attestation_ref(ref: str | None) -> AttestationClass | None:
    """Classify an attestation reference by URI prefix."""
    if not ref:
        return None
    if ref.startswith("mock://"):
        return "mock"
    if ref.startswith("stub://"):
        return "stub"
    return "live"


def certifyedge_mode() -> CertifyEdgeMode:
    """Resolved CertifyEdge execution mode from ``PF_CORE_CERTIFYEDGE_*`` env vars."""
    raw = os.environ.get("PF_CORE_CERTIFYEDGE_MODE", "").strip().lower()
    if raw == "mock":
        return "mock"
    if raw == "live":
        return "live"
    if raw == "auto":
        return "auto"
    if _truthy_env("PF_CORE_CERTIFYEDGE_MOCK") or _truthy_env(_LEGACY_MOCK_ENV):
        return "mock"
    return "auto"


def certifyedge_mock_enabled() -> bool:
    return certifyedge_mode() == "mock"


def _is_format_stub_path(cli: str) -> bool:
    path = Path(cli)
    if path.suffix != ".py" or not path.is_file():
        return False
    name = path.name.lower()
    return "certifyedge-stub" in name or name.endswith("-stub.py")


def _find_live_certifyedge_cli() -> str | None:
    """Resolve a live CertifyEdge binary (never a ``.py`` format-validation stub)."""
    explicit = os.environ.get("PF_CORE_CERTIFYEDGE_CLI", "").strip()
    if explicit and not _is_format_stub_path(explicit):
        path = Path(explicit)
        if path.is_file():
            return str(path)
        resolved = shutil.which(explicit)
        if resolved and not _is_format_stub_path(resolved):
            return resolved
    resolved = shutil.which("certifyedge")
    if resolved and not _is_format_stub_path(resolved):
        return resolved
    return None


def _find_format_stub() -> str | None:
    """Resolve an explicit format-validation stub (``certifyedge-stub.py`` via env only)."""
    explicit = os.environ.get("PF_CORE_CERTIFYEDGE_CLI", "").strip()
    if explicit and _is_format_stub_path(explicit):
        path = Path(explicit)
        if path.is_file():
            return str(path)
    return None


def certifyedge_cli_available() -> bool:
    return _find_live_certifyedge_cli() is not None


def certifyedge_status() -> dict[str, object]:
    """Report CertifyEdge CLI availability for operators and CI."""
    mode = certifyedge_mode()
    live_cli = _find_live_certifyedge_cli()
    stub_cli = _find_format_stub()
    trust_grade = "unpinned"
    pin_identity = None
    try:
        from pcs_core.certifyedge_pin import (
            classify_checker_trust,
            load_certifyedge_pin,
            load_provision_environment,
        )

        pin = load_certifyedge_pin()
        provision = load_provision_environment()
        trust_grade = classify_checker_trust(
            executable=Path(live_cli) if live_cli else None,
            pin=pin,
            provision=provision,
        )
        pin_identity = pin.pin_identity
    except Exception:
        pass
    return {
        "available": live_cli is not None,
        "cli_path": live_cli,
        "format_stub_path": stub_cli,
        "mode": mode,
        "mock_enabled": mode == "mock",
        "live_required": mode == "live" or certifyedge_require_live(),
        "require_live_env": certifyedge_require_live(),
        "allow_stub_env": certifyedge_allow_stub(),
        "trust_grade": trust_grade,
        "pin_identity": pin_identity,
        "env_contract": {
            "PF_CORE_CERTIFYEDGE_MODE": "auto | live | mock (default: auto)",
            "PF_CORE_CERTIFYEDGE_CLI": (
                "optional explicit path to certifyedge binary or stub script"
            ),
            "PF_CORE_CERTIFYEDGE_MOCK": "1 forces mock mode (alias: PCS_CERTIFYEDGE_MOCK)",
            "PF_CORE_CERTIFYEDGE_REQUIRE_LIVE": "1 fails when live CLI absent (release gate)",
            "PF_CORE_CERTIFYEDGE_ALLOW_STUB": "1 allows format stub on require-live (staging only)",
            "PCS_CERTIFYEDGE_PROVISION_ENV": "path to provision.env from provision-certifyedge.sh",
        },
        "install_doc": CERTIFYEDGE_INSTALL_DOC,
    }


def _find_certifyedge_cli() -> str | None:
    """Backward-compatible alias: prefer live CLI, then explicit format stub."""
    return _find_live_certifyedge_cli() or _find_format_stub()


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


def _reject_release_attestation(
    attestation_class: AttestationClass,
    *,
    require_live: bool,
) -> CertificateCheckResult | None:
    """Return a failure result when release-grade attestation class is disallowed."""
    if not require_live:
        return None
    if attestation_class == "mock":
        return CertificateCheckResult(
            ok=False,
            checker="certifyedge",
            checker_version="0.1.0",
            property_id="",
            external_status="Rejected",
            message=(
                "mock attestation rejected when require_live (--require-live or "
                "PF_CORE_CERTIFYEDGE_REQUIRE_LIVE=1)"
            ),
            attestation_class="mock",
            mock=True,
        )
    if attestation_class == "stub" and not certifyedge_allow_stub():
        return CertificateCheckResult(
            ok=False,
            checker="certifyedge",
            checker_version="0.1.0",
            property_id="",
            external_status="Rejected",
            message=(
                "stub attestation rejected on release path; set PF_CORE_CERTIFYEDGE_ALLOW_STUB=1 "
                "only for documented staging exceptions"
            ),
            attestation_class="stub",
            mock=False,
        )
    return None


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

    if attestation_ref is not None:
        explicit_class = classify_attestation_ref(attestation_ref)
        if explicit_class == "mock" and require_live:
            rejected = _reject_release_attestation("mock", require_live=True)
            assert rejected is not None
            return CertificateCheckResult(
                **{
                    **rejected.__dict__,
                    "property_id": property_id,
                    "checker_version": checker_version,
                }
            )

    if mode == "mock":
        if require_live:
            rejected = _reject_release_attestation("mock", require_live=True)
            assert rejected is not None
            return CertificateCheckResult(
                **{
                    **rejected.__dict__,
                    "property_id": property_id,
                    "checker_version": checker_version,
                }
            )
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
            attestation_class="mock",
            mock=True,
            certificate=cert,
        )

    live_cli = _find_live_certifyedge_cli()
    stub_cli = _find_format_stub()
    using_stub = False
    cli: str | None
    if stub_cli is not None:
        cli = stub_cli
        using_stub = True
    elif live_cli is not None:
        cli = live_cli
    else:
        cli = None

    if cli is not None and using_stub and require_live and not certifyedge_allow_stub():
        return CertificateCheckResult(
            ok=False,
            checker="certifyedge",
            checker_version=checker_version,
            property_id=property_id,
            external_status="Rejected",
            message=(
                "PF_CORE_CERTIFYEDGE_MODE=live or --require-live requires live CertifyEdge "
                "CLI (format stub rejected). "
                f"{CERTIFYEDGE_INSTALL_DOC}"
            ),
            attestation_class="stub",
            mock=False,
        )

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
    attestation_class = classify_attestation_ref(resolved_ref) or ("stub" if using_stub else "live")
    rejected = _reject_release_attestation(attestation_class, require_live=require_live)
    if rejected is not None:
        return CertificateCheckResult(
            **{
                **rejected.__dict__,
                "property_id": property_id,
                "checker_version": checker_version,
                "attestation_ref": resolved_ref,
            }
        )

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
    message = (
        "CertifyEdge check-trace succeeded (format stub)"
        if attestation_class == "stub"
        else "CertifyEdge check-trace succeeded (live)"
    )
    return CertificateCheckResult(
        ok=True,
        checker="certifyedge",
        checker_version=checker_version,
        property_id=property_id,
        external_status="CertificateChecked",
        message=message,
        attestation_ref=resolved_ref,
        attestation_class=attestation_class,
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
    attestation_class = result.attestation_class or classify_attestation_ref(result.attestation_ref)
    if require_live and attestation_class in {"mock", "stub"}:
        if attestation_class == "stub" and certifyedge_allow_stub():
            pass
        else:
            raise RuntimeError(
                f"{attestation_class} attestation rejected when require_live: "
                f"{result.attestation_ref}"
            )
    errors = validate_schema(cert, "PFCoreCertificate.v0")
    if errors:
        raise RuntimeError(f"invalid PFCoreCertificate.v0: {'; '.join(errors)}")
    out_path.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
    return result
