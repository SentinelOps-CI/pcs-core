"""Fail-closed org/infrastructure release gates for stable vs preview.

Stable (``PCS_RELEASE_MODE=release``) refuses:

- Unpinned / non-production CertifyEdge pins and untrusted/dev_fixture trust grades
  when live attestation is required
- Missing TrustedKeyRegistry / ArtifactIntegrity signing infrastructure
- Provenance ``attestation.status=gated`` unless ``PCS_PROVENANCE_ALLOW_GATED=true``
  (break-glass only)

Preview may proceed with digest-only integrity, absence notices, and gated
provenance with explicit disclosure. This module does not invent production pins
or private keys.

Operator runbook: ``docs/pf-core/operator-release-gates.md``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pcs_core.artifact_integrity import (
    IntegrityError,
    resolve_trusted_key_registry,
    verify_release_root_signatures,
)
from pcs_core.certifyedge_pin import (
    classify_checker_trust,
    load_certifyedge_pin,
    load_provision_environment,
    pin_is_production_ready,
)
from pcs_core.paths import repo_root
from pcs_core.pf_core_certificate_mode_status import (
    get_certificate_mode_status,
    get_external_claim_class_status,
    load_certificate_mode_status,
)

ReleaseMode = Literal["release", "preview", "dev"]
GateSeverity = Literal["fail", "warn", "info", "pass"]
GateId = Literal[
    "certifyedge_pin",
    "certifyedge_trust_grade",
    "artifact_integrity_registry",
    "artifact_integrity_signatures",
    "provenance_attestation",
    "certificate_mode_policy",
    "oci_cosign_publish",
]


@dataclass(frozen=True)
class GateResult:
    gate_id: GateId
    severity: GateSeverity
    ok: bool
    message: str
    details: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "severity": self.severity,
            "ok": self.ok,
            "message": self.message,
            "details": list(self.details),
        }


@dataclass(frozen=True)
class ReleaseGateReport:
    mode: ReleaseMode
    results: tuple[GateResult, ...]
    allow_gated_provenance: bool = False
    hard_failures: tuple[GateResult, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.hard_failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "v0",
            "artifact_type": "ReleaseGateCheckReport.v0",
            "release_mode": self.mode,
            "ok": self.ok,
            "allow_gated_provenance": self.allow_gated_provenance,
            "results": [r.to_dict() for r in self.results],
            "hard_failures": [r.to_dict() for r in self.hard_failures],
        }


def resolve_release_mode(mode: str | None = None) -> ReleaseMode:
    raw = (mode or os.environ.get("PCS_RELEASE_MODE") or "preview").strip().lower()
    if raw in {"release", "stable"}:
        return "release"
    if raw in {"preview", "dev"}:
        return "preview" if raw == "preview" else "dev"
    raise ValueError(f"unknown release mode {raw!r}; expected release|preview|dev")


def provenance_allow_gated() -> bool:
    return os.environ.get("PCS_PROVENANCE_ALLOW_GATED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _registry_has_release_signing_key(registry: Any) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if not registry.keys:
        return False, ["TrustedKeyRegistry.keys is empty"]
    matching = [k for k in registry.keys if not k.purposes or "release_signing" in k.purposes]
    if not matching:
        return False, [
            "no key with purpose release_signing (or empty purposes allowing all) "
            "in TrustedKeyRegistry"
        ]
    active = [k for k in matching if k.revoked_at is None]
    if not active:
        return False, ["all release_signing keys are revoked"]
    notes.append(f"{len(active)} release_signing key(s) present")
    if registry.registry_id:
        notes.append(f"registry_id={registry.registry_id}")
    return True, notes


def check_certifyedge_pin(
    *,
    mode: ReleaseMode,
    pin_path: Path | None = None,
) -> GateResult:
    path = pin_path or (repo_root() / "pins" / "certifyedge.json")
    try:
        pin = load_certifyedge_pin(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return GateResult(
            gate_id="certifyedge_pin",
            severity="fail",
            ok=False,
            message=f"CertifyEdge pin unreadable: {exc}",
        )
    ready, errors = pin_is_production_ready(pin)
    if mode == "release":
        if not ready:
            return GateResult(
                gate_id="certifyedge_pin",
                severity="fail",
                ok=False,
                message=(
                    "CertifyEdge pin is not production-ready for stable release "
                    f"(status={pin.status!r}, strategy={pin.provision_strategy!r})"
                ),
                details=tuple(errors),
            )
        return GateResult(
            gate_id="certifyedge_pin",
            severity="pass",
            ok=True,
            message=(
                f"CertifyEdge pin production-ready "
                f"(strategy={pin.provision_strategy}, status={pin.status})"
            ),
        )
    if ready:
        return GateResult(
            gate_id="certifyedge_pin",
            severity="pass",
            ok=True,
            message=f"CertifyEdge pin ready (strategy={pin.provision_strategy})",
        )
    return GateResult(
        gate_id="certifyedge_pin",
        severity="info",
        ok=True,
        message=(
            f"CertifyEdge pin not production-ready; allowed in {mode} "
            f"(status={pin.status!r}, strategy={pin.provision_strategy!r})"
        ),
        details=tuple(errors),
    )


def check_certifyedge_trust_grade(*, mode: ReleaseMode) -> GateResult:
    """Fail closed in release when provision.env trust grade is untrusted/unpinned."""
    provision = load_provision_environment()
    try:
        pin = load_certifyedge_pin()
    except (OSError, json.JSONDecodeError, ValueError):
        pin = None

    if provision is None:
        if mode == "release":
            # Pin readiness is covered by check_certifyedge_pin; missing provision.env
            # after a successful pin is still a release blocker when live attestation
            # is required — report as fail so operators run provision-certifyedge.sh.
            ready = False
            if pin is not None:
                ready, _ = pin_is_production_ready(pin)
            if ready:
                return GateResult(
                    gate_id="certifyedge_trust_grade",
                    severity="fail",
                    ok=False,
                    message=(
                        "CertifyEdge pin is production-ready but provision.env is missing; "
                        "run scripts/provision-certifyedge.sh and source provision.env "
                        "before stable live attestation"
                    ),
                )
            return GateResult(
                gate_id="certifyedge_trust_grade",
                severity="info",
                ok=True,
                message="No CertifyEdge provision.env (expected while pin is unpinned)",
            )
        return GateResult(
            gate_id="certifyedge_trust_grade",
            severity="info",
            ok=True,
            message=f"No CertifyEdge provision.env (acceptable in {mode})",
        )

    grade = provision.trust_grade
    if mode == "release" and grade != "pinned":
        return GateResult(
            gate_id="certifyedge_trust_grade",
            severity="fail",
            ok=False,
            message=(
                f"CertifyEdge trust_grade={grade!r}; stable release requires pinned "
                "(dev_fixture / arbitrary PATH checkers are untrusted_development)"
            ),
            details=(
                f"strategy={provision.provision_strategy}",
                f"pin_identity={provision.pin_identity}",
                f"binary_digest={provision.binary_digest}",
            ),
        )

    exe = Path(provision.executable_path) if provision.executable_path else None
    classified = classify_checker_trust(executable=exe, pin=pin, provision=provision)
    return GateResult(
        gate_id="certifyedge_trust_grade",
        severity="pass" if grade == "pinned" else "info",
        ok=True,
        message=f"CertifyEdge trust_grade={grade} (classified={classified})",
        details=(f"strategy={provision.provision_strategy}",),
    )


def check_artifact_integrity_registry(
    *,
    mode: ReleaseMode,
    registry_path: Path | str | None = None,
) -> GateResult:
    try:
        registry = resolve_trusted_key_registry(registry_path)
    except IntegrityError as exc:
        if mode == "release":
            return GateResult(
                gate_id="artifact_integrity_registry",
                severity="fail",
                ok=False,
                message=f"TrustedKeyRegistry invalid: {exc}",
            )
        return GateResult(
            gate_id="artifact_integrity_registry",
            severity="warn",
            ok=True,
            message=f"TrustedKeyRegistry invalid (allowed in {mode}): {exc}",
        )

    if registry is None:
        env_hint = "set PCS_TRUSTED_KEY_REGISTRY to a published TrustedKeyRegistry.v0 JSON"
        if mode == "release":
            return GateResult(
                gate_id="artifact_integrity_registry",
                severity="fail",
                ok=False,
                message=(
                    "TrustedKeyRegistry required for stable ArtifactIntegrity.v1 signing; "
                    + env_hint
                ),
            )
        return GateResult(
            gate_id="artifact_integrity_registry",
            severity="info",
            ok=True,
            message=(
                f"TrustedKeyRegistry absent; digest-only integrity allowed in {mode} ({env_hint})"
            ),
        )

    ok, notes = _registry_has_release_signing_key(registry)
    if not ok:
        if mode == "release":
            return GateResult(
                gate_id="artifact_integrity_registry",
                severity="fail",
                ok=False,
                message="TrustedKeyRegistry present but no usable release_signing key",
                details=tuple(notes),
            )
        return GateResult(
            gate_id="artifact_integrity_registry",
            severity="warn",
            ok=True,
            message="TrustedKeyRegistry present without release_signing key (preview)",
            details=tuple(notes),
        )
    return GateResult(
        gate_id="artifact_integrity_registry",
        severity="pass",
        ok=True,
        message="TrustedKeyRegistry usable for ArtifactIntegrity.v1 release signing",
        details=tuple(notes),
    )


def check_artifact_integrity_signatures(
    *,
    mode: ReleaseMode,
    release_root: Path | None,
    registry_path: Path | str | None = None,
) -> GateResult:
    if release_root is None:
        return GateResult(
            gate_id="artifact_integrity_signatures",
            severity="info",
            ok=True,
            message=(
                "No --release-root; signature verification deferred to assemble/verify "
                "(registry gate still applies in release mode)"
            ),
        )
    if not release_root.is_dir():
        return GateResult(
            gate_id="artifact_integrity_signatures",
            severity="fail",
            ok=False,
            message=f"release root is not a directory: {release_root}",
        )

    try:
        registry = resolve_trusted_key_registry(registry_path)
    except IntegrityError as exc:
        return GateResult(
            gate_id="artifact_integrity_signatures",
            severity="fail",
            ok=False,
            message=f"cannot load TrustedKeyRegistry for signature verify: {exc}",
        )
    if registry is None:
        if mode == "release":
            return GateResult(
                gate_id="artifact_integrity_signatures",
                severity="fail",
                ok=False,
                message="Cannot verify release-root signatures without TrustedKeyRegistry",
            )
        return GateResult(
            gate_id="artifact_integrity_signatures",
            severity="info",
            ok=True,
            message=f"Skipping signature verify (no registry; digest-only in {mode})",
        )

    allow_digest_only = mode != "release"
    errors = verify_release_root_signatures(
        release_root,
        registry,
        allow_digest_only=allow_digest_only,
    )
    hard = [e for e in errors if not e.startswith("DigestOnlyAllowed:")]
    soft = [e for e in errors if e.startswith("DigestOnlyAllowed:")]
    if hard:
        return GateResult(
            gate_id="artifact_integrity_signatures",
            severity="fail",
            ok=False,
            message=f"Release-root ArtifactIntegrity failures under {release_root}",
            details=tuple(hard),
        )
    if soft:
        return GateResult(
            gate_id="artifact_integrity_signatures",
            severity="info",
            ok=True,
            message=f"Digest-only integrity notices under {release_root} ({mode})",
            details=tuple(soft),
        )
    return GateResult(
        gate_id="artifact_integrity_signatures",
        severity="pass",
        ok=True,
        message=f"Release-root ArtifactIntegrity signatures verified under {release_root}",
    )


def _read_provenance_status(provenance_dir: Path) -> tuple[str | None, list[str]]:
    notes: list[str] = []
    binding = provenance_dir / "ReleaseProvenanceBinding.v0.json"
    status_file = provenance_dir / "attestation-status.json"
    status: str | None = None
    if binding.is_file():
        try:
            data = json.loads(binding.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            notes.append(f"unreadable binding: {exc}")
        else:
            att = data.get("attestation") if isinstance(data, Mapping) else None
            if isinstance(att, Mapping):
                status = str(att.get("status") or "") or None
                if status:
                    notes.append(f"binding.attestation.status={status}")
                reason = att.get("gate_reason")
                if reason:
                    notes.append(f"gate_reason={reason}")
    if status_file.is_file():
        try:
            st = json.loads(status_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            notes.append(f"unreadable attestation-status.json: {exc}")
        else:
            file_status = str(st.get("status") or "") or None
            if file_status:
                notes.append(f"attestation-status.json={file_status}")
            if status is None:
                status = file_status
            elif file_status and file_status != status:
                notes.append(f"status mismatch: binding={status!r} status_file={file_status!r}")
    return status, notes


def check_provenance_attestation(
    *,
    mode: ReleaseMode,
    provenance_dir: Path | None,
    allow_gated: bool | None = None,
) -> GateResult:
    allow = provenance_allow_gated() if allow_gated is None else allow_gated
    if provenance_dir is None:
        return GateResult(
            gate_id="provenance_attestation",
            severity="info",
            ok=True,
            message=(
                "No --provenance-dir; provenance status checked when binding is present "
                f"(release forbids gated unless PCS_PROVENANCE_ALLOW_GATED; allow={allow})"
            ),
        )
    if not provenance_dir.is_dir():
        return GateResult(
            gate_id="provenance_attestation",
            severity="fail",
            ok=False,
            message=f"provenance dir is not a directory: {provenance_dir}",
        )

    status, notes = _read_provenance_status(provenance_dir)
    if status is None:
        if mode == "release":
            return GateResult(
                gate_id="provenance_attestation",
                severity="fail",
                ok=False,
                message=(
                    "Provenance package missing attestation status "
                    "(expected ReleaseProvenanceBinding.v0.json attestation.status)"
                ),
                details=tuple(notes),
            )
        return GateResult(
            gate_id="provenance_attestation",
            severity="warn",
            ok=True,
            message="Provenance package present but attestation status missing (preview)",
            details=tuple(notes),
        )

    if status == "signed":
        return GateResult(
            gate_id="provenance_attestation",
            severity="pass",
            ok=True,
            message="Provenance attestation.status=signed",
            details=tuple(notes),
        )

    if status == "gated":
        gated_notice = provenance_dir / "PROVENANCE_ATTESTATION_GATED.json"
        if not gated_notice.is_file():
            return GateResult(
                gate_id="provenance_attestation",
                severity="fail",
                ok=False,
                message="attestation.status=gated without PROVENANCE_ATTESTATION_GATED.json",
                details=tuple(notes),
            )
        if mode == "release" and not allow:
            return GateResult(
                gate_id="provenance_attestation",
                severity="fail",
                ok=False,
                message=(
                    "Stable release forbids gated provenance; enable Sigstore/GHEC "
                    "attestations or set PCS_PROVENANCE_ALLOW_GATED=true only as break-glass"
                ),
                details=tuple(notes),
            )
        severity: GateSeverity = "warn" if mode == "release" else "info"
        return GateResult(
            gate_id="provenance_attestation",
            severity=severity,
            ok=True,
            message=(
                "Provenance attestation.status=gated "
                + (
                    "(PCS_PROVENANCE_ALLOW_GATED break-glass)"
                    if allow
                    else f"(allowed disclosure in {mode})"
                )
            ),
            details=tuple(notes),
        )

    if status == "pending":
        return GateResult(
            gate_id="provenance_attestation",
            severity="fail",
            ok=False,
            message="attestation.status=pending (producer did not finalize signed/gated)",
            details=tuple(notes),
        )

    return GateResult(
        gate_id="provenance_attestation",
        severity="fail",
        ok=False,
        message=f"unknown attestation.status={status!r}",
        details=tuple(notes),
    )


def check_certificate_mode_policy(*, mode: ReleaseMode) -> GateResult:
    try:
        load_certificate_mode_status()
    except Exception as exc:  # noqa: BLE001 — surface table errors as gate failures
        return GateResult(
            gate_id="certificate_mode_policy",
            severity="fail",
            ok=False,
            message=f"certificate mode status table unreadable: {exc}",
        )

    details: list[str] = []
    rc = get_certificate_mode_status("TraceSafeRCertificate")
    if rc is None or str(rc.get("status")) != "release_candidate":
        return GateResult(
            gate_id="certificate_mode_policy",
            severity="fail",
            ok=False,
            message="TraceSafeRCertificate must remain status=release_candidate (sole tool-use RC)",
        )
    details.append("TraceSafeRCertificate=release_candidate")

    for disabled in (
        "HandoffSafeCertificate",
        "ContractCheckedCertificate",
        "EffectFrameCertificate",
        "FramePreservedCertificate",
    ):
        entry = get_certificate_mode_status(disabled)
        if entry is None:
            continue
        if bool(entry.get("allowed_issuance")):
            return GateResult(
                gate_id="certificate_mode_policy",
                severity="fail",
                ok=False,
                message=f"{disabled} must keep allowed_issuance=false while status=disabled",
            )
        details.append(f"{disabled}={entry.get('status')} (issuance closed)")

    experimental = get_certificate_mode_status("CompositionalExtensionCertificate")
    if experimental and str(experimental.get("status")) == "release_candidate":
        return GateResult(
            gate_id="certificate_mode_policy",
            severity="fail",
            ok=False,
            message=(
                "CompositionalExtensionCertificate must not be release_candidate "
                "(experimental only)"
            ),
        )
    if experimental:
        details.append(f"CompositionalExtensionCertificate={experimental.get('status')} (not RC)")

    external = get_external_claim_class_status("CertificateChecked")
    if external:
        details.append(f"external CertificateChecked={external.get('status')}")
        if mode == "release" and str(external.get("status")) == "preview":
            # Informational: CertificateChecked stays preview until CertifyEdge is pinned.
            # The CertifyEdge pin gate already fail-closes live attestation.
            details.append("CertificateChecked remains preview until authenticated CertifyEdge pin")

    return GateResult(
        gate_id="certificate_mode_policy",
        severity="pass",
        ok=True,
        message="Certificate mode policy: TraceSafeRCertificate sole tool-use RC",
        details=tuple(details),
    )


def check_oci_cosign_publish(
    *,
    mode: ReleaseMode,
    require_oci_publish: bool = False,
) -> GateResult:
    """OCI cosign publish is org-infra; advisory unless explicitly required."""
    marker = os.environ.get("PCS_VERIFIER_OCI_DIGEST", "").strip()
    if marker.startswith("sha256:") and len(marker) == 71:
        return GateResult(
            gate_id="oci_cosign_publish",
            severity="pass",
            ok=True,
            message=f"PCS_VERIFIER_OCI_DIGEST set ({marker[:19]}…)",
            details=(
                "Confirm cosign verify + SBOM attestation against GHCR before claiming signed OCI",
            ),
        )
    msg = (
        "Verifier OCI cosign/GHCR publish is org-gated "
        "(see docs/pf-core/operator-release-gates.md); set PCS_VERIFIER_OCI_DIGEST "
        "after publishing by digest"
    )
    if require_oci_publish and mode == "release":
        return GateResult(
            gate_id="oci_cosign_publish",
            severity="fail",
            ok=False,
            message=msg,
        )
    return GateResult(
        gate_id="oci_cosign_publish",
        severity="info",
        ok=True,
        message=msg + f" (advisory in {mode})",
    )


def evaluate_release_gates(
    *,
    mode: str | ReleaseMode | None = None,
    pin_path: Path | None = None,
    registry_path: Path | str | None = None,
    release_root: Path | None = None,
    provenance_dir: Path | None = None,
    allow_gated_provenance: bool | None = None,
    require_oci_publish: bool = False,
) -> ReleaseGateReport:
    resolved = resolve_release_mode(None if mode is None else str(mode))
    allow = provenance_allow_gated() if allow_gated_provenance is None else allow_gated_provenance
    results: list[GateResult] = [
        check_certifyedge_pin(mode=resolved, pin_path=pin_path),
        check_certifyedge_trust_grade(mode=resolved),
        check_artifact_integrity_registry(mode=resolved, registry_path=registry_path),
        check_artifact_integrity_signatures(
            mode=resolved,
            release_root=release_root,
            registry_path=registry_path,
        ),
        check_provenance_attestation(
            mode=resolved,
            provenance_dir=provenance_dir,
            allow_gated=allow,
        ),
        check_certificate_mode_policy(mode=resolved),
        check_oci_cosign_publish(mode=resolved, require_oci_publish=require_oci_publish),
    ]
    hard = tuple(r for r in results if not r.ok and r.severity == "fail")
    return ReleaseGateReport(
        mode=resolved,
        results=tuple(results),
        allow_gated_provenance=allow,
        hard_failures=hard,
    )


def format_report_lines(report: ReleaseGateReport) -> list[str]:
    lines = [
        f"== PCS release gates mode={report.mode} allow_gated={report.allow_gated_provenance} ==",
    ]
    for result in report.results:
        mark = "OK" if result.ok else "FAIL"
        lines.append(f"[{mark}] {result.gate_id}: {result.message}")
        for detail in result.details:
            lines.append(f"       - {detail}")
    if report.ok:
        lines.append(f"OK release gates passed (mode={report.mode})")
    else:
        lines.append(
            f"FAIL release gates ({len(report.hard_failures)} hard failure(s) "
            f"in mode={report.mode})"
        )
    return lines


def run_release_gate_check(
    *,
    mode: str | None = None,
    pin_path: Path | None = None,
    registry_path: Path | str | None = None,
    release_root: Path | None = None,
    provenance_dir: Path | None = None,
    allow_gated_provenance: bool | None = None,
    require_oci_publish: bool = False,
    as_json: bool = False,
) -> tuple[int, str]:
    report = evaluate_release_gates(
        mode=mode,
        pin_path=pin_path,
        registry_path=registry_path,
        release_root=release_root,
        provenance_dir=provenance_dir,
        allow_gated_provenance=allow_gated_provenance,
        require_oci_publish=require_oci_publish,
    )
    if as_json:
        payload = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
        return (0 if report.ok else 1), payload
    text = "\n".join(format_report_lines(report)) + "\n"
    return (0 if report.ok else 1), text


def gate_ids() -> Sequence[GateId]:
    return (
        "certifyedge_pin",
        "certifyedge_trust_grade",
        "artifact_integrity_registry",
        "artifact_integrity_signatures",
        "provenance_attestation",
        "certificate_mode_policy",
        "oci_cosign_publish",
    )
