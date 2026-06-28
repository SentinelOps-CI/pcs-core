# PF-Core merge readiness

Verification log for PF-Core critical-issues fix plan on `main`.

## HEAD CI evidence (2026-06-28)

| Workflow | SHA | Run ID | Result | Notes |
|----------|-----|--------|--------|-------|
| CI | `b5ed639` | 28327689774 | success | Latest `origin/main` at plan start |
| Release chain | `b5ed639` | — | pending | Not observed on latest SHA at fetch; re-run after push |

Prior SHA `038b0bc` had Release chain success; `b5ed639` CI green after Rust catalog fmt parity fix.

## Local verification log (2026-06-28, post fix plan)

| Step | Result |
|------|--------|
| `pytest` PF-Core certificate-mode / catalog / bundle / phase_f | OK |
| `pytest` cross-language + tier1 + stage4 | OK |
| `cargo test pf_core` + clippy | OK (17 passed) |
| `@pcs/core` npm test | OK (27 passed) |
| `python scripts/gen_pf_core_catalog.py` + drift | OK |

## Issue status (critical fix plan)

| Issue | Status | Notes |
|-------|--------|-------|
| #2 Substantive certificate-mode obligations | **fixed** | Aggregate theorems use `And.intro` chains; no `: True := trivial` |
| #3 Catalog `tool_map` generation | **fixed** | Single-source `catalog/pf_core.catalog.json`; generated Python/Rust/TS maps |
| #4 Manual `TOOL_NAME_MAP` removal | **fixed** | Runtime imports generated catalog map |
| #5 `TraceSafeRCertificate` | **fixed** | Tool-use default; resource-scope + `TraceSafeR` obligations |
| #6 CertifyEdge release gates | **fixed** | Release gate requires live/stub attestation; dev CI keeps mock |
| #7 Self-contained release bundles | **fixed** | `kernel_manifest.json` + bundled `kernel/`; validate from bundle |

## Honest deferrals (unchanged)

- Full global non-interference under adversarial schedulers.
- PCS per-obligation Lean term generation (see `docs/pf-core/pcs-envelope-lean-roadmap.md`).
- Live CertifyEdge production deployment beyond stub/CLI matrix (release gate validates format + non-mock attestation).
- WSL duplicate Lean path on Windows hosts without native `lake`.

Reference: `docs/pf-core/claim-boundary.md`, `docs/pf-core/current-gap-audit.md`.
