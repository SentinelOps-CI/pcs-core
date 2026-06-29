# PF-Core merge readiness

Release-ready verification log for PF-Core on `main`.

## Status: release-ready (production gaps B1–B7 + Phase 3)

HEAD evidence recorded after closing production gaps B1–B7, PCS envelope Phase 3, normative certificate-mode resolution vectors (B5), and local release-grade verification on `main`.

## HEAD CI evidence (2026-06-29)

**HEAD SHA:** `ea16683` — CI green ([workflow run 28405144850](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405144850)).

| Job | SHA | Run | Result | Job URL |
|-----|-----|-----|--------|---------|
| python | `ea16683` | 28405144850 | success | [84165796670](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405144850/job/84165796670) |
| lean | `ea16683` | 28405144850 | success | [84165796645](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405144850/job/84165796645) |
| pf-core-adapter | `ea16683` | 28405144850 | success | [84165796626](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405144850/job/84165796626) |
| rust | `ea16683` | 28405144850 | success | [84165796648](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405144850/job/84165796648) |
| typescript | `ea16683` | 28405144850 | success | [84165796633](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405144850/job/84165796633) |
| validate-cli-contract | `ea16683` | 28405144850 | success | [84166200583](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405144850/job/84166200583) |

**Release chain:** [28403151442](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28403151442) at `4f6cf34` (success; doc-only commits after this SHA do not re-trigger release-chain path filters).

**PF-Core Release Gate:** [28405143541](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405143541) (`workflow_dispatch` on `main` at `ea16683`) and [28405303036](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405303036) (tag `v0.1.0-pf-core` push) — **expected failure** without live CertifyEdge CLI (`PF_CORE_CERTIFYEDGE_CLI` secret or `certifyedge` on PATH). Staging exception: `PF_CORE_CERTIFYEDGE_ALLOW_STUB=1` with `--require-live` (documented in `certifyedge-ci.md`). Live attestation remains an external ops dependency.

**Local matrix (2026-06-29, Windows native `lake`):** `scripts/pf-core-release-grade-local.ps1` — all steps green; pytest `-k pf_core` 295 passed, 3 skipped; certificate-mode resolution vectors 5 passed; `cargo test pf_core` 21 passed; `npm test` 28 passed; `pcs conformance run --suite pf-core --release-grade` OK; `bundle-release` + `validate-bundle` OK; CertifyEdge mock + stub dry-runs OK (dev only).

**Release verify:** `scripts/run-release-verify.sh` requires Linux/macOS/Git Bash with native `lake` (full matrix including isolated bundle validation + adversarial invalid-fixture sweep). Not executed on Windows CI agent; local Windows verification uses `pf-core-release-grade-local.ps1` (includes B6 fixture via conformance and invalid-fixture runner).

## Production gaps closure (2026-06-29)

| Gap | Status | Evidence |
|-----|--------|----------|
| B1 CertifyEdge live/stub/mock | **done** | `AttestationClass` in `pf_core_certifyedge.py`; release gate requires live CLI; `docs/pf-core/certifyedge-ci.md`; `test_pf_core_phase_f.py` |
| B2 Release-grade mode policy | **done** | `workflow_certificate_modes` in catalog; `resolve_certificate_mode(..., release_grade=True)` skips sibling heuristic; Rust/TS generated map; cross-language tests |
| B3 TraceSafeR sole tool-use path | **done** | Release-grade lean-check/codegen/conformance require `TraceSafeRCertificate` + `concrete_trace_safe_r*`; `claim-boundary.md` |
| B5 Certificate-mode resolution vectors | **done** | `python/tests/hash_vectors/pf_core/certificate_mode_resolution/vectors.json`; `test_pf_core_certificate_mode_resolution_vectors.py` |
| B6 ContractChecked missing contract file | **done** | `examples/pf-core-invalid/certificate_mode_contractcheckedcertificate_missing_contract_file/`; `check_pf_core_invalid_fixtures` |
| B7 Doc sync | **done** | This file, gap audit, README, certifyedge-ci; `pcs pf-core audit-claims` |
| Phase 3 PCS envelope lean | **done** | `pcs-envelope.generated-lean-proof` subcheck; multi-artifact `witnessResultHashesAdmissibleD` codegen |
| Phase 4 research | **documented** | v0.2 backlog in `non-interference.md` and gap audit — no claim upgrade |

## Six-step critical issues plan (2026-06-29)

| Step | Status | Evidence |
|------|--------|----------|
| 1. Latest-head evidence | **done** | Six CI jobs at `ea16683` [28405144850](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405144850); release-chain [28403151442](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28403151442) |
| 2. TraceSafeRCertificate by policy | **done** | Trace field, WorkflowProfile, catalog `workflow_certificate_modes`; release-grade rejects base `TraceSafeCertificate` for tool-use |
| 3. Fully self-contained bundles | **done** | `bundle-release` / `validate-bundle`; isolated temp-dir test in release verify |
| 4. Release-only CertifyEdge | **done** | Release gate: live CLI required; mock/stub rejected on release path |
| 5. Adversarial certificate-mode fixtures | **done** | Seven mode-specific invalid fixtures under `examples/pf-core-invalid/certificate_mode_*` |
| 6. Freeze claim boundary | **done** | `README.md`, `claim-boundary.md`, this document |

## Phase 1 — Release cut (2026-06-29)

| Task | Status | Notes |
|------|--------|-------|
| Tag `v0.1.0-pf-core` | **done** | Points to release SHA after hardening commits; CI green before tag move |
| CHANGELOG | **done** | PF-Core v0.1.0-pf-core section |
| Local bundle-release | **done** | `pcs pf-core bundle-release` + `validate-bundle` on tool-use fixture |
| GitHub Release | **done** | [v0.1.0-pf-core](https://github.com/SentinelOps-CI/pcs-core/releases/tag/v0.1.0-pf-core) with bundle tarball attached |

## Bounded claim

PF-Core provides machine-checkable trace certificates for a bounded, catalog-driven, resource-pattern-scoped subset of agentic tool-use traces.

## Local verification matrix

| Check | Command | Result (2026-06-29) |
|-------|---------|------------------------|
| PF-Core pytest | `pytest -q -k pf_core` | 295 passed, 3 skipped |
| Certificate-mode vectors | `pytest -q tests/test_pf_core_certificate_mode_resolution_vectors.py` | 5 passed |
| PCS Lean codegen | `pytest -q tests/test_pcs_lean_codegen.py` | pass |
| Release-grade conformance | `pcs conformance run --suite pf-core --release-grade` | OK |
| Rust parity | `cargo test pf_core` | 21 passed |
| TypeScript parity | `npm test` (@pcs/core) | 28 passed |
| Release-grade local matrix | `scripts/pf-core-release-grade-local.ps1` | all steps green (native `lake`) |
| Release verify | `scripts/run-release-verify.sh` | Linux/macOS/Git Bash matrix |
| Claims audit | `pcs pf-core audit-claims` | exit 0 |

## Bundle release (v0.1.0-pf-core)

From repository root with native `lake` on PATH:

```bash
pcs pf-core lean-check --release-grade \
  --trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json \
  --out /tmp/pfcore-cert.json
pcs pf-core bundle-release \
  --trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json \
  --cert /tmp/pfcore-cert.json \
  --out release-bundle/
pcs pf-core validate-bundle release-bundle/
```

Validate the bundle in an empty temp directory (no repo checkout) before attaching to a GitHub Release.

## Honest deferrals

- Full global non-interference under adversarial schedulers (v0.2+ research; see `non-interference.md`).
- PCS tool-use Lean path does not discharge PF-Core `TraceSafeR` — remains separate (`pcs pf-core lean-check`).
- Live CertifyEdge production deployment beyond CLI/secret matrix on release gate.
- Rust/TS do not emit `LeanKernelChecked` certificates (Python lean-check only).

Reference: `docs/pf-core/claim-boundary.md`, `docs/pf-core/current-gap-audit.md`, `docs/pf-core/release-checklist.md`.
