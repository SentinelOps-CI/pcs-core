# PF-Core merge readiness

Release-ready verification log for PF-Core on `main`.

## Status: release-ready

All six critical-issue plan steps verified on HEAD (`9724c6b`, 2026-06-29). No code fixes required — blockers referenced at `b5ed639` are resolved on current main. Local release-grade matrix passes with native `lake` on Windows.

## HEAD CI evidence (2026-06-29)

| Workflow | SHA | Run ID | Result | Notes |
|----------|-----|--------|--------|-------|
| CI | `9724c6b` | 28330791563 | success | HEAD on main; all CI jobs green |
| Release chain | `9724c6b` | 28330791564 | success | `validate-release-chain` green |

Prior fix commits (already on main): `21d1575` (And.intro mode obligations), `d24162f`/`15eb268` (CertifyEdge + ruff), catalog `tool_map` generation, kernel bundle manifest.

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

## Full release-grade local proof (2026-06-29)

| Step | Result | Notes |
|------|--------|-------|
| `scripts/pf-core-release-grade-local.ps1` | OK | Full matrix (285 pytest, lake PFCore+PCS, lean-check, bundle, rust, CertifyEdge mock+stub) |
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

## Six-step critical issues audit (2026-06-29, HEAD `9724c6b`)

| Step | Audit | Evidence |
|------|-------|----------|
| 1. Release evidence | **already done** | CI + Release chain green on `9724c6b`; local `pf-core-release-grade-local.ps1` all steps OK |
| 2. Marker theorems | **already done** | Grep `: True := trivial` clean on `lean/PFCore/Generated/` and codegen; `lean_and_intro_theorem` emits `And.intro` chains |
| 3. TraceSafeRCertificate | **already done** | 7 modes in schema/codegen; `MODE_OBLIGATION_THEOREMS` includes `concrete_trace_safe_r*`; tool-use default via `tool_use_trace.json` sibling |
| 4. tool_map | **already done** | `catalog/pf_core.catalog.json` `tool_map`; generated `pf_core_catalog.py`/Rust/TS; runtime imports catalog (no manual map) |
| 5. Kernel in bundles | **already done** | `build_kernel_manifest()` per-file sha256; `kernel/` copied into bundle; `validate-bundle` validates from manifest not checkout |
| 6. CertifyEdge release hardening | **already done** | `PF_CORE_CERTIFYEDGE_REQUIRE_LIVE`, `--require-live`, release gate rejects `mock://`; dev CI mock path preserved |

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
