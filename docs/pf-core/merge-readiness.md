# PF-Core merge readiness

Verification log for PF-Core critical-issues fix plan on `main`.

## HEAD CI evidence (2026-06-28)

| Workflow | SHA | Run ID | Result | Notes |
|----------|-----|--------|--------|-------|
| CI | `d24162f` | 28328871492 | **failure** | `python` ruff F401 unused `DEFAULT_CERTIFICATE_MODE` in `lean_check.py`; `validate-cli-contract` skipped (upstream) |
| Release chain | `d24162f` | 28328871501 | success | `validate-release-chain` green |
| CI | `15eb268` | 28328983600 | success | Fix: remove unused import; all jobs green |
| Release chain | `15eb268` | 28328983599 | success | `validate-release-chain` green |

### Job matrix (`d24162f`, run 28328871492)

| Job | Result |
|-----|--------|
| python | **failure** |
| lean | success |
| rust | success |
| typescript | success |
| pf-core-adapter | success |
| validate-cli-contract | skipped |

### Job matrix (`15eb268`, run 28328983600)

| Job | Result |
|-----|--------|
| python | success |
| lean | success |
| rust | success |
| typescript | success |
| pf-core-adapter | success |
| validate-cli-contract | success |

Fix commit: `15eb268` — Remove unused lean_codegen import so ruff passes on main CI.

Prior SHA `b5ed639` CI run 28327689774 was green; `038b0bc` had Release chain success.
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
