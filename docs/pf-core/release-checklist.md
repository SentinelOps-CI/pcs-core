# PF-Core release checklist

Pre-release verification for PF-Core in `pcs-core`. Run from repository root unless noted.

## Mandatory CI matrix (blocking jobs)

Separate blocking jobs. Prefer requiring `CI matrix gate` / `Distribution matrix gate` in branch protection, or list each job below.

### `.github/workflows/ci.yml`

| Job | Proves |
|-----|--------|
| `Python full tests` | Full pytest, ruff, schemas, audits, conformance, benchmarks, catalog drift |
| `Python full-package typecheck` | `pyright pcs_core` (full package) |
| `Python branch coverage` | Branch coverage on full suite; fail-under on trust-critical modules |
| `Rust fmt/clippy/tests/fuzz-smoke` | `cargo fmt` / clippy / tests + proptest smoke (`rust/FUZZING.md`) |
| `TypeScript lint/tests/property-vectors` | `npm run lint` / `test` / `test:hash-vectors` |
| `Lean PCS build` | `lake build PCS` |
| `Lean PF-Core build` | `lake build PFCore` + lean-check + proof-binding + validate-contracts |
| `Certificate-mode end-to-end` | Mode status/codegen/resolution + handoff/contract/effect-frame/transition evidence |
| `Cross-language differential` | Python/Rust/TS parity + `pf-core-cross-language` conformance |
| `Semantic-projection replay` | PCS projection binding + PF-Core projection/TCB + bundle verify |
| `Theorem-manifest replay` | `PFCoreTheoremManifest.v0` binding / replay |
| `Scientific payload mutation` | ResultArtifact payload bytes + computation mutation fixtures |
| `Signature and key-revocation` | ArtifactIntegrity Ed25519 + pin + external attestation |
| `Preview release workflow` | lean-check → bundle → validate → absence notice → upload |
| `Stable release dry-run` | In-repo bundle dry-run + mock rejection; **live CertifyEdge gated** on pin + `secrets.PF_CORE_CERTIFYEDGE_CLI` |
| `Provenance verification` | Digest binding + consumer verify; **signed attestations gated** on org OIDC / GHEC |
| `Validate CLI contract` | Required CLI smoke (after Python tests) |
| `CI matrix gate` | Aggregator over the jobs above |
| `PF-Core adapter parity` | Adapter pin parity (`continue-on-error` off `main` only) |

### `.github/workflows/distribution.yml`

| Job | Proves |
|-----|--------|
| `Validator-wheel clean install` | Schema/semantic OK; Lean unavailable |
| `Verifier-wheel clean install` | Bundled Lean assets + lean-check + bundle/verify |
| `Verifier OCI Dockerfile pin` | Base digest + non-root user |
| `Verifier OCI clean execution` | `docker build` + capabilities + lean-check (`scripts/test-verifier-oci.sh`) |
| `Distribution matrix gate` | Aggregator |

### Release / provenance workflows

| Workflow / job | Proves | Gating |
|----------------|--------|--------|
| `release.yml` parallel quality jobs | Same matrix as CI quality lanes | Always on tag / `workflow_dispatch` |
| `release.yml` → `Preview/stable release assemble` | lean-check → bundle → attest/absence → provenance | Live CertifyEdge + signed provenance require pin/secrets/OIDC |
| `release.yml` → `Consumer provenance verify` | Clean-consumer provenance verify | Signed require when producer status=`signed` |
| `pf-core-release-gate.yml` | Live CertifyEdge (release) or preview path | `secrets.PF_CORE_CERTIFYEDGE_CLI` / pinned provision |
| `release-provenance.yml` | Standalone produce + consumer verify | Signed path gated on org attestation capability |

### Detailed pytest / CLI mapping

| Job / step | Proves |
|------------|--------|
| `pytest tests/test_pf_core_tier1.py` | semantics_layer, PCS envelope alias, negative vectors |
| `pytest tests/test_pf_core_handoff_evidence.py` | Handoff delegated_capabilities fidelity + explicit handoff_ids |
| `pytest tests/test_pf_core_contract_evidence.py` | Contract semantics_layer projection + ContractChecked binding |
| `pytest tests/test_pf_core_effect_frame_evidence.py` | Independent PFCoreEffectFrame.v0 + non-tautological EffectFrameCertificate |
| `pytest tests/test_pf_core_transition_evidence.py` | FramePreserved stepState witnesses + cross-tenant no-op reject |
| `pytest tests/test_pf_core_cross_language.py` | Python/Rust/TS parity on shared vectors |
| `pcs pf-core audit-claims` | No forbidden overclaim phrases in docs/examples |
| `pcs pf-core audit-boundary` | Trusted-boundary docs and registry consistency |
| `pcs pf-core audit-lean-catalog` | Catalog symbols exist in Lean sources |
| `pcs pf-core audit-lean-no-sorry` | No `sorry` / `axiom` in `lean/PFCore/` |
| `pcs examples check` | Valid/invalid PF-Core fixtures including replay and isolation |
| Lean job: `lake build PFCore` | Kernel compiles; decider soundness theorems check |
| Lean job: `pcs pf-core lean-check` | Concrete trace proof + `LeanKernelChecked` path on fixture; prints deterministic artifact paths |
| Lean job: `validate-contracts` | Contract runtime checker on `contract_checked/` |
| `pcs pf-core bundle-release` / `validate-bundle` / `verify-bundle` | Closed release bundle with projection, theorem manifest, evidence digests; validate=structural; verify=replay+Lean compile (required for stable) |
| Mode status table | `schemas/pf_core.certificate_mode_status.json` — public claim surface; disabled modes fail closed |
| `python scripts/gen_pf_core_catalog.py` in CI | Generated catalog artifacts match `catalog/pf_core.catalog.json` |
| `scripts/pf-core-release-grade-local.{ps1,sh}` | Full local release-grade matrix: pytest sweep, catalog drift, audit-lean-no-sorry, PFCore+PCS lake, lean-check (`TraceSafeRCertificate`), bundle kernel manifest, CertifyEdge mock+stub |

## Local verification matrix

Run from repository root unless noted. Each row maps a release-checklist gate to a local command.

| Gate | Local command | Evidence |
|------|---------------|----------|
| Tier 1 semantics + negative vectors | `cd python && pytest -q tests/test_pf_core_tier1.py` | pytest pass |
| Cross-language parity | `cd python && pytest -q tests/test_pf_core_cross_language.py` | pytest pass |
| Cross-language conformance | `pcs conformance run --suite pf-core-cross-language` | suite pass |
| Claims audit | `pcs pf-core audit-claims` | exit 0 |
| Boundary audit | `pcs pf-core audit-boundary` | exit 0 |
| Lean catalog audit | `pcs pf-core audit-lean-catalog` | exit 0 |
| No sorry/axiom | `pcs pf-core audit-lean-no-sorry` | exit 0 |
| Example fixtures | `pcs examples check` | exit 0 |
| PF-Core conformance | `pcs conformance run --suite pf-core --release-grade` | suite pass (requires lake/WSL) |
| Lean kernel build | `cd lean && lake build PFCore` | exit 0 |
| PCS envelope kernel | `cd lean && lake build PCS` | exit 0 |
| Concrete trace proof | `pcs pf-core lean-check --trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json --result-out /tmp/lean-check.json` | `LeanKernelChecked` certificate + LeanCheckResult |
| Contract runtime checker | `pcs pf-core validate-contracts examples/pf-core-valid/contract_checked/trace.json --contracts-dir examples/pf-core-valid/contract_checked` | exit 0 |
| Release bundle | `pcs pf-core bundle-release --trace ... --cert ... --lean-check-result ... --out /tmp/bundle` then `pcs pf-core validate-bundle /tmp/bundle` and `pcs pf-core verify-bundle /tmp/bundle` | closed manifest includes projection/theorem/evidence/lean-check hashes; verify-bundle required for stable |
| Mode status table | `pytest -q tests/test_pf_core_certificate_mode_status.py` | disabled modes fail closed |
| Catalog drift | `python scripts/gen_pf_core_catalog.py && git diff --exit-code python/pcs_core/pf_core_catalog.py lean/PFCore/Catalog.lean rust/crates/pcs-core/src/pf_core_catalog.rs typescript/packages/core/src/pfCoreCatalog.ts` | no diff |
| Rust PF-Core | `cd rust && cargo test pf_core -q` | all pass |
| TypeScript PF-Core | `cd typescript/packages/core && npm test` | all pass |
| PCS Lean codegen | `cd python && pytest -q tests/test_pcs_lean_codegen.py` | pass; prop theorems in `lean/PCS/Generated/` |
| Compositional trust | `cd python && pytest -q tests/test_pf_core_compositional.py tests/test_pf_core_research.py` | pass |
| CertifyEdge mock | `scripts/pf-core-certifyedge-dry-run.ps1` (or `.sh`) | mock attestation |
| CertifyEdge stub | `scripts/pf-core-certifyedge-stub-dry-run.ps1` (or `.sh`) | `stub://` + `checker_version` |
| Full matrix | `scripts/pf-core-release-grade-local.ps1` (or `.sh`) | all steps green |
| Org/infra release gates | `pcs release check-gates --mode preview` (stable: `--mode release`) | preview pass; release fail-closed until pins/keys/attestations |

## Local full demo

```bash
pip install -e python
bash scripts/pf-core-bridge-demo.sh
pcs pf-core lean-check --trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json
pcs pf-core validate-contracts \
  examples/pf-core-valid/contract_checked/trace.json \
  --contracts-dir examples/pf-core-valid/contract_checked
PCS_CERTIFYEDGE_MOCK=1 pcs pf-core certifyedge-check \
  --trace examples/pf-core-valid/labtrust_replay/trace.json \
  --property qc_release.temporal.safety \
  --out /tmp/PFCoreCertificate.certifyedge.json
```

Optional Lean build (requires Lean 4 + `lake`):

```bash
cd lean && lake build PFCore
```

Release-grade local path (conformance + proof binding + full lean-check when lake/WSL available):

```bash
bash scripts/pf-core-release-grade-local.sh
```

On Windows without native `lake`, use WSL for Lean steps.

## Claim boundaries for external release

| Claim class | May state | Must not state |
|-------------|-----------|----------------|
| `RuntimeChecked` | Python deciders aligned with Lean predicates | Lean kernel proof, CertifyEdge attestation |
| `LeanKernelChecked` | Concrete `traceSafeD` (+ contract deciders when refs present) proved in Lean | Global non-interference, full JSON contract discharge for role/policy/evidence fields |
| `ReplayValidated` | Hash-chain integrity | Upgrades to Lean or CertifyEdge |
| `CertificateChecked` | External checker attestation (CertifyEdge mock or live) | `LeanKernelChecked`, global non-interference |

Reference: `docs/pf-core/claim-boundary.md`, `docs/pf-core/non-interference.md`, `docs/pf-core/contract-semantics.md`.

## Phase F deliverables (this release)

- F1: `NonInterference.lean` + `validate_tenant_isolation` + `cross_tenant_leak/` fixture
- F2: `ContractDecide.lean` + Lean codegen contract discharge for mapped JSON fields
- F3: `pf_core_certifyedge.py` + `pcs pf-core certifyedge-check` + mock CI path

## GitHub release gate dry-run (no tag push)

These steps mirror CI without pushing a tag or committing.

### PF-Core release gate (`workflow_dispatch` or tag)

Workflow file: `.github/workflows/pf-core-release-gate.yml`

**Tag dry-run (no push):** create a local annotated tag only, or use `workflow_dispatch` on branch `main` — do not push `v*` tags until sign-off below is complete.

1. Open GitHub → Actions → **PF-Core Release Gate** → **Run workflow** (branch: `main`, or select a release candidate branch).
2. Alternatively, push tag `v0.1.x` only after local `scripts/pf-core-release-grade-local.{ps1,sh}` and release-chain validation pass.
2. The job installs `python/` and runs CertifyEdge with `PF_CORE_CERTIFYEDGE_REQUIRE_LIVE=1` and `--require-live`.
3. Live CLI resolution order: `secrets.PF_CORE_CERTIFYEDGE_CLI` → `certifyedge` on PATH. No automatic stub fallback on the release path.
4. Success criteria: `/tmp/PFCoreCertificate.certifyedge.release.json` validates; attestation is not `mock://`; `stub://` rejected unless `PF_CORE_CERTIFYEDGE_ALLOW_STUB=1`; `checker` and `checker_version` present.

Local equivalent (stub format contract):

```powershell
powershell -File scripts/pf-core-certifyedge-stub-dry-run.ps1
```

Local mock dev path (not accepted as release attestation):

```powershell
powershell -File scripts/pf-core-certifyedge-dry-run.ps1
```

### Release chain workflow

Workflow file: `.github/workflows/release-chain.yml` (also exercised in `ci.yml`).

Local equivalent from repository root:

```bash
pcs validate-release-chain examples/labtrust-release/
pcs validate-release-chain examples/tool-use-release/
pcs validate-release-chain examples/computation-release/
```

### Full local release-grade (recommended pre-tag)

```powershell
powershell -File scripts/pf-core-release-grade-local.ps1
```

```bash
bash scripts/pf-core-release-grade-local.sh
```

## Final sign-off (local, pre-tag)

Complete before tagging; record date and operator in this section (local edit only).

Org/infrastructure gates (CertifyEdge pin, TrustedKeyRegistry, signed provenance, cosign OCI):
see [operator-release-gates.md](operator-release-gates.md). Stable check:

```bash
pcs release check-gates --mode release
```

| Gate | Command | Pass (Y/N) | Date | Notes |
|------|---------|------------|------|-------|
| Full release-grade matrix | `scripts/pf-core-release-grade-local.{ps1,sh}` | Y | 2026-06-29 | Windows native `lake` |
| Release-chain protocol | `pcs validate-release-chain examples/{labtrust,tool-use,computation}-release/` | Y | 2026-06-29 | |
| PCS Lean codegen | `pytest tests/test_pcs_lean_codegen.py` | Y | 2026-06-29 | Included in pf_core pytest sweep |
| Cross-language parity | `pytest tests/test_pf_core_cross_language.py`; `cargo test pf_core`; `npm test` | Y | 2026-06-29 | 21 Rust, 28 TS |
| Catalog drift | `python scripts/gen_pf_core_catalog.py && git diff --exit-code ...` | Y | 2026-06-29 | |
| No sorry/axiom | `pcs pf-core audit-lean-no-sorry` | Y | 2026-06-29 | |
| CertifyEdge stub dry-run | `scripts/pf-core-certifyedge-stub-dry-run.ps1` | Y | 2026-06-29 | |
| README PF-Core section accurate | Manual review | Y | 2026-06-29 | TraceSafeR + CertifyEdge classes |
| Honest deferrals unchanged or updated | `docs/pf-core/merge-readiness.md` | Y | 2026-06-29 | v0.2 backlog documented |

**2026-06-29 sign-off (`ea16683`):** All automated gates in rows 1–7 passed on Windows native `lake`. B1–B7 + B5 certificate-mode vectors + Phase 3 PCS lean-proof complete. GitHub Release [v0.1.0-pf-core](https://github.com/SentinelOps-CI/pcs-core/releases/tag/v0.1.0-pf-core) with bundle. Release gate [28405143541](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405143541) fails without live CertifyEdge (expected); staging via `PF_CORE_CERTIFYEDGE_ALLOW_STUB=1`.
