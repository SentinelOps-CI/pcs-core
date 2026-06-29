# PF-Core merge readiness

Release-ready verification log for PF-Core on `main`.

## Status: release-ready (six-step critical issues plan)

HEAD evidence recorded after executing the six-step PF-Core critical issues plan on `main`.

## HEAD CI evidence (2026-06-29)

| Workflow | SHA | Run ID | Result | Notes |
|----------|-----|--------|--------|-------|
| CI | `c121103` | [28363685794](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28363685794) | success | Prior HEAD before plan execution |
| Release chain | `c121103` | [28363685824](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28363685824) | success | `validate-release-chain` green |

Post-plan local verification re-run on working tree (2026-06-29): pytest `-k pf_core` 287 passed; `pcs conformance run --suite pf-core --release-grade` OK; `cargo test pf_core` 19 passed; `npm test` 28 passed.

## Six-step critical issues plan (2026-06-29)

| Step | Status | Evidence |
|------|--------|----------|
| 1. Latest-head evidence | **done** | `git fetch origin`; HEAD `c121103`; CI + Release chain URLs above; local conformance release-grade OK |
| 2. TraceSafeRCertificate by policy | **done** | `required_certificate_mode` on `PFCoreTrace.v0`; `resolve_certificate_mode` prefers trace policy; release-grade lean-check rejects tool-use traces resolving to `TraceSafeCertificate` only; Rust/TS parity |
| 3. Fully self-contained bundles | **done** | `bundle-release` copies `lean-toolchain`, `lean/lakefile.lean`, `lean/lake-manifest.json`, kernel tree, proof, trace, cert; `validate-bundle` hashes from bundled contents only; isolated temp-dir test |
| 4. Release-only CertifyEdge | **done** | `.github/workflows/pf-core-release-gate.yml` requires live/stub attestation on `v*` tags; dev CI keeps mock (`mock://` rejected on release path) |
| 5. Adversarial certificate-mode fixtures | **done** | Six mode-specific invalid fixtures under `examples/pf-core-invalid/certificate_mode_*`; wired via `check_pf_core_invalid_fixtures` and release-grade conformance |
| 6. Freeze claim boundary | **done** | Bounded claim in `README.md`, `claim-boundary.md`, this document |

## Bounded claim

PF-Core provides machine-checkable trace certificates for a bounded, catalog-driven, resource-pattern-scoped subset of agentic tool-use traces.

## Local verification matrix

| Check | Command | Result (2026-06-29) |
|-------|---------|------------------------|
| PF-Core pytest | `pytest -q -k pf_core` | 287 passed, 3 skipped |
| Release-grade conformance | `pcs conformance run --suite pf-core --release-grade` | OK |
| Rust parity | `cargo test pf_core` | 19 passed |
| TypeScript parity | `npm test` (@pcs/core) | 28 passed |
| Release-grade local matrix | `scripts/pf-core-release-grade-local.ps1` | Run on hosts with native `lake` |
| Release verify | `scripts/run-release-verify.sh` | Linux/macOS/Git Bash matrix |

## Honest deferrals

- Full global non-interference under adversarial schedulers.
- PCS computation witness full `witnessResultHashesAdmissible` codegen.
- PCS tool-use Lean codegen does not discharge PF-Core `TraceSafeR` / resource-scope kernel proofs.
- Live CertifyEdge production deployment beyond stub/CLI matrix.
- Rust/TS do not emit `LeanKernelChecked` certificates (Python lean-check only).

Reference: `docs/pf-core/claim-boundary.md`, `docs/pf-core/current-gap-audit.md`, `docs/pf-core/release-checklist.md`.
