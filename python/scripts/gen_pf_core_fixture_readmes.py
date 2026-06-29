"""Generate thin README.md files for PF-Core certificate-mode fixtures."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

ADVERSARIAL = [
    (
        "certificate_mode_tracesafercertificate_resource_scope_on_allow",
        "TraceSafeRCertificate",
        "Allow event resource path outside capability pattern scope.",
    ),
    (
        "certificate_mode_framepreservedcertificate_invalid_frame_transition",
        "FramePreservedCertificate",
        "Invalid effect-frame transition between allow events.",
    ),
    (
        "certificate_mode_effectframecertificate_undeclared_effect",
        "EffectFrameCertificate",
        "Write effect not declared in effect frame footprint.",
    ),
    (
        "certificate_mode_handoffsafecertificate_delegated_expansion",
        "HandoffSafeCertificate",
        "Delegated capability exceeds source principal authority.",
    ),
    (
        "certificate_mode_compositionalextensioncertificate_unsafe_extension",
        "CompositionalExtensionCertificate",
        "Unsafe trace append breaks compositional safety invariant.",
    ),
    (
        "certificate_mode_contractcheckedcertificate_failed_precondition",
        "ContractCheckedCertificate",
        "Contract precondition fails for mapped trace event.",
    ),
]

VALID_MODES = [
    (
        "certificate_mode_tracesafecertificate",
        "TraceSafeCertificate",
        "Base trace-safe certificate mode (non-tool-use).",
    ),
    (
        "certificate_mode_tracesafercertificate",
        "TraceSafeRCertificate",
        "Resource-pattern-scoped trace-safe certificate mode.",
    ),
    (
        "certificate_mode_framepreservedcertificate",
        "FramePreservedCertificate",
        "Effect-frame preservation obligations.",
    ),
    (
        "certificate_mode_effectframecertificate",
        "EffectFrameCertificate",
        "Effect frame discharge for allow events.",
    ),
    (
        "certificate_mode_handoffsafecertificate",
        "HandoffSafeCertificate",
        "Handoff authority preservation.",
    ),
    (
        "certificate_mode_compositionalextensioncertificate",
        "CompositionalExtensionCertificate",
        "Compositional trace extension safety.",
    ),
    (
        "certificate_mode_contractcheckedcertificate",
        "ContractCheckedCertificate",
        "JSON contract discharge for mapped fields.",
    ),
]


def write_readme(path: Path, title: str, body_lines: list[str]) -> None:
    if path.is_file():
        return
    path.write_text("\n".join([f"# {title}", ""] + body_lines + [""]), encoding="utf-8")


def main() -> None:
    for slug, mode, desc in ADVERSARIAL:
        case_dir = REPO / "examples" / "pf-core-invalid" / slug
        manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
        write_readme(
            case_dir / "README.md",
            slug.replace("_", " ").title(),
            [
                (
                    f"Intentionally invalid PF-Core adversarial fixture for "
                    f"**`{mode}`** certificate mode."
                ),
                "",
                desc,
                "",
                f"- **Expected error:** `{manifest['expected_error']}`",
                f"- **Fail stage:** `{manifest['must_fail_at']}`",
                "",
                "Used by `check_pf_core_invalid_fixtures()` and "
                "`pcs conformance run --suite pf-core --release-grade`.",
            ],
        )

    for slug, mode, desc in VALID_MODES:
        case_dir = REPO / "examples" / "pf-core-valid" / slug
        if not case_dir.is_dir():
            continue
        write_readme(
            case_dir / "README.md",
            f"Valid {mode} fixture",
            [
                (
                f"Valid PF-Core trace exercising **`{mode}`** "
                "certificate-mode codegen obligations."
            ),
                "",
                desc,
                "",
                "Regenerate via `python/scripts/gen_certificate_mode_fixtures.py` when "
                "certificate-mode obligations change.",
            ],
        )


if __name__ == "__main__":
    main()
