"""PF-Core claim-boundary linter and Lean catalog audit."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pcs_core.lean_catalog import (
    LEAN_THEOREM_CATALOG,
    PF_CORE_THEOREM_CATALOG,
    PF_CORE_TRUSTED_LEAN_DIR,
)
from pcs_core.paths import examples_dir, repo_root
from pcs_core.registry_data import PF_CORE_CLAIM_CLASSES, pf_core_artifact_types

FORBIDDEN_PHRASES: tuple[tuple[str, str], ...] = (
    ("verified agent", "trace-level safety preservation under stated assumptions"),
    ("guarantees ai safety", "contracted action safety under stated assumptions"),
    ("model is safe", "schema-validated runtime observation"),
    (
        "agent is safe",
        "Lean-kernel-checked trace theorem (only when claim_class is LeanKernelChecked)",
    ),
    ("fully verified runtime", "runtime-checked trace with explicit claim class"),
    (
        "formally verified platform",
        "release-envelope consistency theorem family (for PCS Lean scope)",
    ),
)

_SCAN_SUFFIXES = {".md", ".json", ".txt", ".rst"}
_CLAIM_BOUNDARY_DOC = Path("docs") / "pf-core" / "claim-boundary.md"
_THEOREM_RE = re.compile(r"^\s*theorem\s+([A-Za-z0-9_]+)", re.MULTILINE)


@dataclass(frozen=True)
class ClaimViolation:
    path: str
    phrase: str
    replacement: str
    line: int


@dataclass(frozen=True)
class BoundaryIssue:
    code: str
    message: str


def _scan_roots() -> list[Path]:
    roots = [repo_root() / "docs", examples_dir()]
    return [path for path in roots if path.is_dir()]


def _iter_scan_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in _SCAN_SUFFIXES:
            files.append(path)
    return sorted(files)


def _relative_repo_path(path: Path) -> str:
    root = repo_root()
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def audit_claims() -> list[ClaimViolation]:
    violations: list[ClaimViolation] = []
    for root in _scan_roots():
        for path in _iter_scan_files(root):
            rel = Path(_relative_repo_path(path))
            if rel.as_posix() == _CLAIM_BOUNDARY_DOC.as_posix():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            lower = text.lower()
            for phrase, replacement in FORBIDDEN_PHRASES:
                start = 0
                while True:
                    index = lower.find(phrase, start)
                    if index < 0:
                        break
                    line = text.count("\n", 0, index) + 1
                    violations.append(
                        ClaimViolation(
                            path=_relative_repo_path(path),
                            phrase=phrase,
                            replacement=replacement,
                            line=line,
                        )
                    )
                    start = index + len(phrase)
    return violations


def audit_boundary() -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []

    claim_boundary = repo_root() / "docs" / "pf-core" / "claim-boundary.md"
    if not claim_boundary.is_file():
        issues.append(BoundaryIssue("missing_claim_boundary_doc", str(claim_boundary)))
    else:
        text = claim_boundary.read_text(encoding="utf-8")
        from pcs_core.registry_data import (
            PF_CORE_CERTIFICATE_CLAIM_CLASSES,
            PF_CORE_TRACE_CLAIM_CLASSES,
        )

        for claim_class in sorted(PF_CORE_TRACE_CLAIM_CLASSES):
            if f"`{claim_class}`" not in text and claim_class not in text:
                issues.append(
                    BoundaryIssue(
                        "trace_claim_class_undocumented",
                        f"PFCoreTraceClaimClass {claim_class!r} missing from claim-boundary.md",
                    )
                )
        for claim_class in sorted(PF_CORE_CERTIFICATE_CLAIM_CLASSES):
            if f"`{claim_class}`" not in text and claim_class not in text:
                issues.append(
                    BoundaryIssue(
                        "certificate_claim_class_undocumented",
                        f"PFCoreCertificateClaimClass {claim_class!r} missing from claim-boundary.md",
                    )
                )

    registry_types = pf_core_artifact_types()
    expected = {
        "PFCorePrincipal.v0",
        "PFCoreCapability.v0",
        "PFCoreResource.v0",
        "PFCoreAction.v0",
        "PFCoreEvent.v0",
        "PFCoreTrace.v0",
        "PFCoreContract.v0",
        "PFCoreHandoff.v0",
        "PFCoreCertificate.v0",
        "PFCoreRuntimeObservation.v0",
    }
    missing_registry = expected - registry_types
    for artifact_type in sorted(missing_registry):
        issues.append(
            BoundaryIssue(
                "missing_registry_entry",
                f"registry_data.py missing entry for {artifact_type}",
            )
        )

    mission = repo_root() / "docs" / "pf-core" / "mission.md"
    if mission.is_file():
        mission_text = mission.read_text(encoding="utf-8")
        required = (
            "PF-Core is the minimal trusted action-trace kernel inside PCS. "
            "PCS defines evidence containers and release-chain artifacts; PF-Core "
            "defines the formal semantics of agentic actions, contracted traces, "
            "and trace-level safety preservation."
        )
        if required not in mission_text:
            issues.append(
                BoundaryIssue("missing_mission_sentence", "mission.md missing required sentence")
            )
    else:
        issues.append(BoundaryIssue("missing_mission_doc", str(mission)))

    return issues


def _lean_sources() -> list[Path]:
    lean_dir = repo_root() / "lean"
    if not lean_dir.is_dir():
        return []
    return sorted(lean_dir.rglob("*.lean"))


def _collect_lean_theorem_names(*, pfcore_only: bool = False) -> set[str]:
    names: set[str] = set()
    lean_dir = repo_root() / "lean"
    if not lean_dir.is_dir():
        return names
    sources = sorted(lean_dir.rglob("*.lean"))
    if pfcore_only:
        pfcore = lean_dir / "PFCore"
        sources = sorted(pfcore.glob("*.lean")) if pfcore.is_dir() else []
    for path in sources:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        names.update(_THEOREM_RE.findall(text))
    return names


def audit_lean_catalog() -> list[str]:
    """Return error messages for trusted catalog theorems missing from Lean sources."""
    errors: list[str] = []
    lean_theorems = _collect_lean_theorem_names()
    if not lean_theorems and _lean_sources():
        errors.append("Could not parse any theorem names from lean/**/*.lean")

    for theorem in sorted(LEAN_THEOREM_CATALOG):
        if theorem not in lean_theorems:
            errors.append(
                f"Lean theorem {theorem!r} listed in LEAN_THEOREM_CATALOG "
                f"but absent from lean/**/*.lean"
            )

    pfcore_theorems = _collect_lean_theorem_names(pfcore_only=True)
    pfcore_dir = repo_root() / "lean" / "PFCore"
    if not pfcore_dir.is_dir():
        errors.append(f"PF-Core Lean directory missing: {PF_CORE_TRUSTED_LEAN_DIR}/")
    elif not pfcore_theorems:
        errors.append(f"Could not parse any theorem names from {PF_CORE_TRUSTED_LEAN_DIR}/")

    for theorem in sorted(PF_CORE_THEOREM_CATALOG):
        if theorem not in pfcore_theorems:
            errors.append(
                f"Lean theorem {theorem!r} listed in PF_CORE_THEOREM_CATALOG "
                f"but absent from {PF_CORE_TRUSTED_LEAN_DIR}/"
            )
    return errors
