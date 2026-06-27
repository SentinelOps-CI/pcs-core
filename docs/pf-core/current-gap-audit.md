# PF-Core gap audit

Summary of gaps between the PF-Core vision and the current `pcs-core` repository.

## Tier 1 — production trusted kernel (complete)

**Status:** Tier 1 production kernel: complete (uncommitted)

| Item | Status | Notes |
|------|--------|-------|
| `semantics_layer` on `PFCoreContract.v0` | Done | Flat field map: `lean` / `runtime` / `out_of_scope`; validator defaults |
| `contract_semantics_checked` on certificates | Done | Derived from semantics layers + checks |
| Cross-language semantic parity | Done | Rust `pf_core.rs`, TS `pfCore.ts`, `conformance run --suite pf-core-cross-language` |
| Trace vs certificate claim classes | Done | Separate enums; traces reject `LeanKernelChecked` / `CertificateChecked` |
| Direct-trace effect catalog | Done | Closed `effect_kind` enum + semantic validators |
| `proof_term_hash` on certificates | Done | sha256 of generated `.lean` bytes before `lake env lean` |
| Full semantic validation in lean-check | Done | `validate_artifact` on emitted certificates |
| Generated-lean-proof conformance | Done | Subcheck in `conformance run --suite pf-core` |
| `pcs pcs-envelope check` | Done | Alias; `pcs lean-check` deprecated with notice |
| PCS envelope-only framing (choice B) | Done | No `LeanKernelChecked` on PCS path; docs + tests |
| CertifyEdge live-then-mock CI | Done | `pf_core_certifyedge.py`; CI mock fallback |
| `scripts/run-pf-core-adapter-ci.sh` | Done | Pinned provability-fabric-core hash parity |
| Tier 1 tests | Done | `test_pf_core_tier1.py` |

## Tier 2 — documented deferrals (complete)

| Item | Status | Notes |
|------|--------|-------|
| Full global non-interference | Deferred | `non-interference.md` |
| Lean RoleMap / role encoding | Deferred | Permanent assumption in `assumptions.md` |
| Full Lean role/policy/evidence contract encoding | Deferred | Runtime-only fields in semantics_layer |

## Tier 3 — operational (complete)

| Item | Status | Notes |
|------|--------|-------|
| Gap audit (this file) | Done | |
| `generated-proofs.md` | Done | Regeneration policy for `lean/PFCore/Generated/` |
| `CHANGELOG.md` PF-Core section | Done | |
| `windows-lean.md` | Done | elan / WSL guide |

## Protocol and schemas

| Gap | Status | Notes |
|-----|--------|-------|
| PF-Core artifact JSON schemas | Done | Stage 2 |
| `LeanCheckResult.v0` JSON schema | Done | Stage 4 |
| PFCoreCertificate proof artifacts | Done | Stage 4 |
| Replay certificate fields | Done | Stage 5 |
| ToolUseTrace optional `handoffs` | Done | Stage 7 |

## Lean kernel

| Gap | Status | Notes |
|-----|--------|-------|
| Release-envelope theorems | Present | `lean/PCS/Theorems.lean` |
| Agent safety predicates (`EventSafe`, `TraceSafe`) | Done | Stage 3 `lean/PFCore/` |
| Concrete Lean proof terms per trace obligation | Done | Stage 4 codegen + `lake env lean` |
| Handoff non-expansion (`HandoffSafe`) | Done | `lean/PFCore/Handoff.lean` + runtime |

## Validation and claims

| Gap | Status | Notes |
|-----|--------|-------|
| `pcs pf-core lean-check` CLI | Done | Stage 3–4 |
| `pcs pf-core replay-trace` | Done | Stage 5 |
| `pcs pf-core validate-contracts` | Done | Stage 7 |
| Contract satisfaction runtime checker | Done | `pf_core_contract.py` |
| Resource scope enforcement | Done | Stage 7 deciders + trace validation |
| Handoff preservation in trace compiler | Done | Stage 7 optional `handoffs` |
| PCS release-envelope path clarity | Done | `pcs pcs-envelope check`; lean-check deprecated |

## Remaining research (deferred)

1. **Compositional trust theorems** — see [compositional-trust-roadmap.md](compositional-trust-roadmap.md).
2. **Full provability-fabric-core live adapter orchestration** — hash parity covered natively via adapter CI script; full cross-repo orchestration remains optional.
3. **Full agent runtime, MCP, NL policy, model safety** — out of scope.
4. **Global non-interference** — see `non-interference.md`.

## Phase F (research-grade extensions)

| Item | Status | Notes |
|------|--------|-------|
| F1 — Conservative tenant non-interference | Done | `NonInterference.lean`, `validate_tenant_isolation` |
| F2 — JSON contract discharge in Lean codegen | Done | `ContractDecide.lean`, `contract-semantics.md` |
| F3 — CertifyEdge hook + mock CI | Done | `pf_core_certifyedge.py` |
| Release checklist + theorem sheet | Done | `release-checklist.md` |

### Honest limitations (Phase F + Tier 2)

- Tenant theorems cover **allowed events in safe traces**, not global cross-tenant non-interference.
- Lean contract discharge maps capability, effect, tenant, decision, event_safe, trace_safe only; role/policy/evidence refs remain runtime-only (`semantics_layer`).
- CertifyEdge live CLI depends on external install; CI uses mock when absent.
- PKI is documented out of scope for v0.1 only.
