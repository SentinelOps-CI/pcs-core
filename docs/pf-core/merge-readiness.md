# PF-Core merge readiness

Release-ready verification log for PF-Core on `main` (local uncommitted session 2026-06-28).

## Status: release-ready (local verification)

All critical issues #1-7 addressed. Local release-grade matrix passes with native `lake` on Windows. Changes in this session are **uncommitted** per operator request.

## HEAD CI evidence (2026-06-28)

| Workflow | SHA | Run ID | Result | Notes |
|----------|-----|--------|--------|-------|
| CI | `6a6efe6` | 28329193168 | success | HEAD on main; all CI jobs green |
| Release chain | `6a6efe6` | (paired) | success | `validate-release-chain` green |

Prior fix commits: `15eb268` (ruff import), `6a6efe6` (UTF-8 encoding).

## Local verification matrix (A-G plan)

| Plan item | Status | Local command | Result |
|-----------|--------|---------------|--------|
| A. PCS per-obligation Lean | **incremental** | `pytest tests/test_pcs_lean_codegen.py`; `lake build PCS` | Component prop theorems (`*_prop`) for all three release-chain obligations; tool-use/computation codegen deferred |
| B. Compositional trust | **complete** | `pytest tests/test_pf_core_compositional.py tests/test_pf_core_research.py` | All roadmap theorems proved in Lean; runtime tests pass |
| C. Release checklist | **complete** | See `docs/pf-core/release-checklist.md` local matrix | Every gate has local command |
| D. Cross-language parity | **complete** | `pytest tests/test_pf_core_cross_language.py`; `cargo test pf_core`; `npm test` | TraceSafeRCertificate, tool_map, mode obligations, resource scope, cross-tenant, NI |
| E. Examples and conformance | **complete** | `pcs examples check`; `pcs conformance run --suite pf-core --release-grade` | 18/18 pf-core-valid dirs have manifests |
| F. Merge-readiness bundle | **complete** | This document | Verification matrix populated |
| G. CertifyEdge live path (stub) | **complete** | `scripts/pf-core-certifyedge-stub-dry-run.ps1` | `stub://` attestation, `checker_version`, attestation in `assumption_refs` |

## Full release-grade local proof

| Step | Result | Notes |
|------|--------|-------|
| `scripts/pf-core-release-grade-local.ps1` | OK | Full matrix |
| All `test_pf_core_*.py` | OK | pytest sweep |
| `pytest -k pf_core` | OK | PF-Core subset |
| Certificate-mode codegen (no `: True := trivial`) | OK | grep clean on `lean/PFCore/Generated/` |
| Catalog `tool_map` drift | OK | `gen_pf_core_catalog.py` + git diff |
| `pcs pf-core audit-lean-no-sorry` | OK | PFCore + PCS scope |
| `lake build PFCore` + `lake build PCS` | OK | Native lake on Windows |
| `lean-check` tool-use trace | OK | Default `TraceSafeRCertificate`; substantive `concrete_trace_safe_r*` |
| `bundle-release` / `validate-bundle` | OK | `kernel_manifest.json` + bundled `kernel/` |
| CertifyEdge mock + stub dry-run | OK | Mock dev path; stub format contract |
| Rust/TS `TOOL_NAME_MAP` + mode default parity | OK | `resolve_tool_mapping` / `resolveCertificateModeDefault` |
| `cargo test pf_core` | OK | Rust parity tests |
| `npm test` (@pcs/core) | OK | TypeScript parity tests |
| `pcs conformance run --suite pf-core --release-grade` | OK | Release-grade conformance |
| PCS Lean codegen prop theorems | OK | Three component `*_prop` + aggregate in `lean/PCS/Generated/` |

## Issue status (critical fix plan)

| Issue | Status | Notes |
|-------|--------|-------|
| #2 Substantive certificate-mode obligations | **fixed** | Aggregate theorems use `And.intro` chains; no `: True := trivial` |
| #3 Catalog `tool_map` generation | **fixed** | Single-source `catalog/pf_core.catalog.json`; generated Python/Rust/TS maps |
| #4 Manual `TOOL_NAME_MAP` removal | **fixed** | Runtime imports generated catalog map |
| #5 `TraceSafeRCertificate` | **fixed** | Tool-use default; resource-scope + `TraceSafeR` obligations |
| #6 CertifyEdge release gates | **fixed** | Release gate requires live/stub attestation; dev CI keeps mock |
| #7 Self-contained release bundles | **fixed** | `kernel_manifest.json` + bundled `kernel/`; validate from bundle |

## Cross-language parity summary (D)

| Capability | Python | Rust | TypeScript |
|------------|--------|------|------------|
| `TraceSafeRCertificate` mode default (tool-use) | yes | yes | yes |
| Mode obligation theorem lists (6 modes) | yes | yes | yes |
| `resolve_tool_mapping` / catalog `tool_map` | yes | yes | yes |
| Resource scope validation | yes | yes | yes |
| Cross-tenant safety decider | yes | yes | yes |
| Observational NI decider | yes | yes | yes |
| `contract_semantics_checked` on certificates | yes | yes | yes |
| `kernel_manifest` bundle validate | yes | n/a (Python CLI) | n/a |
| Lean kernel proof emission | yes | no (by design) | no (by design) |

## Honest deferrals

- Full global non-interference under adversarial schedulers.
- PCS tool-use / computation witness Lean codegen (predicates exist; no fixture path yet).
- Live CertifyEdge production deployment beyond stub/CLI matrix.
- WSL duplicate Lean path on Windows hosts without native `lake`.
- Rust/TS do not emit `LeanKernelChecked` certificates (Python lean-check only).

Reference: `docs/pf-core/claim-boundary.md`, `docs/pf-core/current-gap-audit.md`, `docs/pf-core/pcs-envelope-lean-roadmap.md`.
