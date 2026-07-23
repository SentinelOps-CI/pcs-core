"""Machine-readable PF-Core certificate mode claim-surface status (A0).

Authoritative table: ``schemas/pf_core.certificate_mode_status.json``.
Disabled modes fail closed under ``--release-grade`` and the default public CLI.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from pcs_core.paths import schemas_dir

MODE_STATUS_FILENAME = "pf_core.certificate_mode_status.json"
MODE_STATUSES = frozenset({"release_candidate", "legacy", "disabled", "experimental", "preview"})
# Public CLI may issue these when allowed_issuance is true.
PUBLIC_CLI_STATUSES = frozenset({"release_candidate", "legacy", "experimental"})
# Release-grade issuance is limited to RC + legacy (non-tool-use).
RELEASE_GRADE_STATUSES = frozenset({"release_candidate", "legacy"})


class CertificateModeStatusError(ValueError):
    """Raised when the mode-status table is missing or malformed."""


@lru_cache(maxsize=1)
def certificate_mode_status_path() -> Path:
    path = schemas_dir() / MODE_STATUS_FILENAME
    if not path.is_file():
        raise CertificateModeStatusError(f"missing certificate mode status table: {path}")
    return path


@lru_cache(maxsize=1)
def load_certificate_mode_status() -> dict[str, Any]:
    path = certificate_mode_status_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CertificateModeStatusError(f"unreadable mode status table {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CertificateModeStatusError(f"mode status table root must be an object: {path}")
    modes = data.get("modes")
    if not isinstance(modes, list) or not modes:
        raise CertificateModeStatusError(f"mode status table missing modes[]: {path}")
    seen: set[str] = set()
    for entry in modes:
        if not isinstance(entry, dict):
            raise CertificateModeStatusError("modes[] entries must be objects")
        mode = str(entry.get("mode") or "")
        status = str(entry.get("status") or "")
        if not mode:
            raise CertificateModeStatusError("modes[] entry missing mode")
        if mode in seen:
            raise CertificateModeStatusError(f"duplicate mode in status table: {mode!r}")
        if status not in MODE_STATUSES:
            raise CertificateModeStatusError(
                f"mode {mode!r} has unknown status {status!r}; "
                f"expected one of {sorted(MODE_STATUSES)}"
            )
        if "allowed_issuance" not in entry or not isinstance(entry["allowed_issuance"], bool):
            raise CertificateModeStatusError(f"mode {mode!r} requires boolean allowed_issuance")
        if "description" not in entry or not str(entry.get("description") or "").strip():
            raise CertificateModeStatusError(f"mode {mode!r} requires description")
        seen.add(mode)
    return data


def iter_mode_status_entries() -> list[dict[str, Any]]:
    data = load_certificate_mode_status()
    modes = data["modes"]
    assert isinstance(modes, list)
    return [dict(entry) for entry in modes if isinstance(entry, dict)]


def mode_status_by_name() -> dict[str, dict[str, Any]]:
    return {str(entry["mode"]): entry for entry in iter_mode_status_entries()}


def get_certificate_mode_status(mode: str) -> dict[str, Any] | None:
    return mode_status_by_name().get(mode)


def get_external_claim_class_status(claim_class: str) -> dict[str, Any] | None:
    data = load_certificate_mode_status()
    entries = data.get("external_claim_classes") or []
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and str(entry.get("claim_class") or "") == claim_class:
            return dict(entry)
    return None


def enforce_certificate_mode_issuance(
    mode: str,
    *,
    release_grade: bool = False,
    allow_non_public: bool = False,
) -> str | None:
    """Return an error message when public / release-grade issuance must fail closed.

    Codegen and fixture generators may pass ``allow_non_public=True``. The default
    public CLI and ``--release-grade`` paths must leave it false.
    """
    if allow_non_public:
        return None
    entry = get_certificate_mode_status(mode)
    if entry is None:
        return f"unknown certificate_mode {mode!r} (not present in mode status table)"
    status = str(entry.get("status") or "")
    allowed = bool(entry.get("allowed_issuance"))
    if not allowed:
        return (
            f"certificate mode {mode!r} is {status}; public issuance refused "
            "(allowed_issuance=false in schemas/pf_core.certificate_mode_status.json)"
        )
    if status not in PUBLIC_CLI_STATUSES:
        return (
            f"certificate mode {mode!r} status {status!r} is not issuable via the "
            f"default public CLI (allowed: {sorted(PUBLIC_CLI_STATUSES)})"
        )
    if release_grade and status not in RELEASE_GRADE_STATUSES:
        return (
            f"certificate mode {mode!r} status {status!r} is not allowed under "
            f"--release-grade (allowed: {sorted(RELEASE_GRADE_STATUSES)})"
        )
    return None


def public_issuance_modes(*, release_grade: bool = False) -> frozenset[str]:
    """Modes that may be issued under the stated policy."""
    allowed: set[str] = set()
    for entry in iter_mode_status_entries():
        mode = str(entry["mode"])
        if enforce_certificate_mode_issuance(mode, release_grade=release_grade) is None:
            allowed.add(mode)
    return frozenset(allowed)


def mode_status_summary_lines() -> list[str]:
    lines: list[str] = []
    for entry in sorted(iter_mode_status_entries(), key=lambda e: str(e["mode"])):
        lines.append(
            f"{entry['mode']}: status={entry['status']} "
            f"allowed_issuance={entry['allowed_issuance']}"
        )
    external = get_external_claim_class_status("CertificateChecked")
    if external:
        lines.append(
            f"external CertificateChecked: status={external['status']} "
            f"allowed_issuance={external['allowed_issuance']}"
        )
    return lines


def assert_status_table_covers_modes(known_modes: Mapping[str, Any] | frozenset[str]) -> None:
    """Fail if CERTIFICATE_MODES and the status table drift apart."""
    table_modes = set(mode_status_by_name())
    known = set(known_modes)
    missing = known - table_modes
    extra = table_modes - known
    if missing or extra:
        raise CertificateModeStatusError(
            "certificate mode status table drift: "
            f"missing_from_table={sorted(missing)} extra_in_table={sorted(extra)}"
        )
