# PF-Core merge readiness

Release-ready verification log for PF-Core on `main`.

## Status: release-ready (production gaps plan complete)

HEAD evidence recorded after B1–B7 production hardening, Phase 3 PCS envelope lean-proof, and release-cut preparation on `main`.

## HEAD CI evidence (2026-06-29)

| Workflow | SHA | Run ID | Result | Notes |
|----------|-----|--------|--------|-------|
| CI | `d327d07` | pending | — | Ruff lint fix after `e061495` CI failure |
| Release chain | `e061495` | [28402655648](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28402655648) | success | B6 adversarial fixture |
| CI (prior) | `93625a1` | [28400984580](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28400984580) | success | Six-step plan baseline |
| Release chain (prior) | `93625a1` | [28400984561](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28400984561) | success | `validate-release-chain` green |

Post-hardening local verification (2026-06-29, HEAD `d327d07`): pytest `-k "pf_core or pcs_lean_codegen"` 305 passed, 3 skipped; `pcs conformance run --suite pf-core --release-grade` OK; `cargo test pf_core` 21 passed; `npm test` 28 passed; `pcs pf-core audit-claims` OK; `pcs pf-core lean-check --release-grade` + `bundle-release` + `validate-bundle` OK on native `lake`.

## Production hardening plan (B1–B7, 2026-06-29)

| Item | Status | Evidence |
|------|--------|----------|
| B1 — CertifyEdge live/stub/mock | **done** | `a31a347`; `AttestationClass`; release gate rejects mock without `PF_CORE_CERTIFYEDGE_ALLOW_STUB` |
| B2 — workflow_certificate_modes catalog | **done** | `1fadcfd`; release-grade `resolve_certificate_mode` skips sibling heuristic |
| B3 — TraceSafeR sole tool-use LeanKernelChecked path | **done** | `748601d`; release-grade lean-check/codegen/conformance enforce R obligations |
| B6 — ContractChecked missing contract fixture | **done** | `e061495`; `certificate_mode_contractcheckedcertificate_missing_contract_file/` |
| B7 — Documentation sync | **done** | This document, gap audit, README, audit-claims |
| Phase 3 — PCS envelope lean-proof | **done** | `0aaee97`; PCS generated-lean-proof conformance; multi-artifact witness codegen |

## Six-step critical issues plan (2026-06-29)

| Step | Status | Evidence |
|------|--------|----------|
| 1. Latest-head evidence | **done** | CI + Release chain URLs above; local conformance release-grade OK |
| 2. TraceSafeRCertificate by policy | **done** | `required_certificate_mode` on trace; `WorkflowProfile` + catalog `workflow_certificate_modes`; release-grade rejects base `TraceSafeCertificate` only |
| 3. Fully self-contained bundles | **done** | `bundle-release` copies toolchain, lake files, kernel tree; `validate-bundle` isolated |
| 4. Release-only CertifyEdge | **done** | `pf-core-release-gate.yml`; mock/stub rejected on release path unless explicit staging flag |
| 5. Adversarial certificate-mode fixtures | **done** | Seven mode-specific invalid fixtures including B6 contract-file gap |
| 6. Freeze claim boundary | **done** | Bounded claim in `README.md`, `claim-boundary.md`, this document |

## Phase 0 — Evidence (2026-06-29)

| Task | Status | Notes |
|------|--------|-------|
| HEAD table refresh | **done** | SHA + CI links in table above |
| Release gate workflow_dispatch | **documented** | See `release-checklist.md` PF-Core Release Gate section; trigger Actions → PF-Core Release Gate → Run workflow on `main` |
| Local matrix | **done** | `scripts/pf-core-release-grade-local.ps1` / `.sh`; results in Local verification matrix below |
| Sign-off tables | **done** | `release-checklist.md`, `production-kernel-checklist.md` |
| Release verify | **done** | `scripts/run-release-verify.sh` on Linux/Git Bash; isolated bundle + invalid-fixture steps |

## Phase 1 — Release cut (2026-06-29)

| Task | Status | Notes |
|------|--------|-------|
| Tag `v0.1.0-pf-core` | **pending** | At final green HEAD after CI on lint fix |
| CHANGELOG | **done** | `CHANGELOG.md` PF-Core v0.1.0-pf-core section |
| Local bundle-release | **done** | `pcs pf-core bundle-release` + `validate-bundle` on tool-use fixture; native `lake` |
| GitHub Release assets | **ops** | Attach bundle after tag push + release-gate workflow |

## Bounded claim

PF-Core provides machine-checkable trace certificates for a bounded, catalog-driven, resource-pattern-scoped subset of agentic tool-use traces. Release-grade tool-use `LeanKernelChecked` requires the TraceSafeR evidence chain (refinement to base TraceSafe via `traceSafeR_implies_traceSafe`).

## Local verification matrix

| Check | Command | Result (2026-06-29) |
|-------|---------|------------------------|
| PF-Core pytest | `pytest -q -k "pf_core or pcs_lean_codegen"` | 305 passed, 3 skipped |
| Release-grade conformance | `pcs conformance run --suite pf-core --release-grade` | OK |
| Rust parity | `cargo test pf_core` | 21 passed |
| TypeScript parity | `npm test` (@pcs/core) | 28 passed |
| Claims audit | `pcs pf-core audit-claims` | OK |
| Release-grade lean-check + bundle | `pcs pf-core lean-check --release-grade` + `bundle-release` + `validate-bundle` | OK (native `lake`) |
| Release-grade local matrix | `scripts/pf-core-release-grade-local.ps1` | Run on hosts with native `lake` |
| Release verify | `scripts/run-release-verify.sh` | Linux/macOS/Git Bash matrix |

## Honest deferrals (v0.2+)

- Full global non-interference under adversarial schedulers (see `non-interference.md` v0.2 backlog).
- Full JSON contract Lean discharge for role/policy/evidence refs.
- Write footprint ↔ effect linkage as derived kernel theorem.
- Live provability-fabric-core orchestration beyond adapter hash parity.
- Rust/TS do not emit `LeanKernelChecked` certificates (Python lean-check only).
- PCS tool-use Lean codegen does not discharge PF-Core TraceSafeR (separate `pcs pf-core lean-check` path).

Reference: `docs/pf-core/claim-boundary.md`, `docs/pf-core/current-gap-audit.md`, `docs/pf-core/release-checklist.md`, `docs/pf-core/non-interference.md`.
