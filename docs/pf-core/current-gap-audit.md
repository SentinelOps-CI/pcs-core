# PF-Core gap audit

Summary of gaps between the PF-Core vision and the current `pcs-core` repository.

## Tier 1 — production trusted kernel (complete)

**Status:** Tier 1 production kernel: complete (uncommitted)

| Item | Status | Notes |
|------|--------|-------|
| `semantics_layer` on `PFCoreContract.v0` | Done | Flat field map: `lean` / `runtime` / `out_of_scope`; validator defaults |
| `contract_semantics_checked` on certificates | Done | Derived from semantics layers + checks |
| Cross-language semantic parity | Done | Rust `pf_core.rs`, TS `pfCore.ts`, `conformance run --suite pf-core-cross-language` |
| Rust/TS direct-trace effect/capability parity | Done (uncommitted) | `validate_direct_trace_action_semantics` / `validateDirectTraceActionSemantics`; error codes `UnknownEffect`, `UnknownCapability`, `CapabilityEffectMismatch` |
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
| Full global non-interference | Partial | `TraceCrossTenantSafe` link in `NonInterference.lean`; full global NI still open |
| Lean RoleMap / role encoding | Partial | `runtimeRoleMap` parity with Python; kernel still uses explicit capabilities |
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

## Phase H (research: state, cross-tenant NI, RoleMap parity)

| Item | Status | Notes |
|------|--------|-------|
| H1 — Rich operational state + handoff | Done | `Transition.lean`, `State.lean`; `stepState`, frames, strong handoff lemmas |
| H2 — `TenantIsolation` + `TraceCrossTenantSafe` | Partial | `traceSafe_implies_tenant_isolation`; covert channels / timing open |
| H3 — `runtimeRoleMap` Python parity | Done | `RoleMap.lean` + `test_pf_core_research.py` |
| H4 — Research catalog tests | Done | `test_pf_core_research.py`, `test_pf_core_research_grade.py`, catalog updates |
| H5 — Effect frames | Done | `EffectFrame.lean`; write exclusion under explicit footprint alignment |
| H6 — Contract refinement | Done | `ContractRefinement`, `contract_refinement_preserves_trace_safe` |
| H7 — Replay claim boundary | Done | `replay_preserves_claim_boundary` in `pf_core_replay.py` |

## Remaining research (deferred)

1. **Full global cross-tenant non-interference** — conservative tenant isolation for allowed events is proved; covert channels, timing, deny-side leaks open (`non-interference.md`).
2. **Write footprint ↔ effect linkage** — `WriteFootprintRequiresWriteEffect` explicit; derived from `ActionAdmissible` + `KnownCapabilityEffect` for catalog capabilities.
3. **Resource-pattern scope in Lean** — Python `validate_resource_scope` and certificate `contract_semantics_checked.runtime` (`resource_pattern_scope`); `ResourcePattern.lean` provides decider parity; not discharged in Lean trace safety kernel.
4. **Full provability-fabric-core live adapter orchestration** — hash parity covered natively via adapter CI script.
5. **Full agent runtime, MCP, NL policy, model safety** — out of scope.

## External audit remediation (2026-06)

| Blocker | Status | Notes |
|---------|--------|-------|
| Lean `file_write_capability_aligns_write_footprint` soundness | Done | `KnownCapability` / `KnownCapabilityEffect` on `ActionAdmissible` |
| Resource-pattern scope certificate boundary | Done | `contract_semantics_checked.runtime` + claim-boundary doc |
| Conformance `--release-grade` for pf-core | Done | Fail closed without lake/WSL; verify-proof-binding gate |
| `run-release-verify.sh` release path | Done | Runtime smoke vs full lean-check + verify-proof-binding |
| CI lean job elan PATH + verify-proof-binding | Done | `.github/workflows/ci.yml` |
| Cross-language invalid hash vectors | Done | trace/previous hash mismatch, cross-tenant leak |
| TypeScript CI npm install in cross-language tests | Done | pytest + conformance suites |

## Phase G (compositional trust + proof binding)

| Item | Status | Notes |
|------|--------|-------|
| G1 — Compositional Lean layer | Done | `Compositional.lean`: safe extension, handoff chain, contract seq invariants |
| G2 — Minimal RoleMap Lean | Done | `RoleMap.lean`: alignment → `HasCapability` |
| G3 — `verify-proof-binding` CLI | Done | `pcs pf-core verify-proof-binding` |
| G4 — Compositional tests | Done | `test_pf_core_compositional.py` |

## Phase F (research-grade extensions)

| Item | Status | Notes |
|------|--------|-------|
| F1 — Conservative tenant non-interference | Done | `NonInterference.lean`, `validate_tenant_isolation` |
| F2 — JSON contract discharge in Lean codegen | Done | `ContractDecide.lean`, `contract-semantics.md` |
| F3 — CertifyEdge hook + mock CI | Done | `pf_core_certifyedge.py` |
| Release checklist + theorem sheet | Done | `release-checklist.md` |

## Phase I — Trust-boundary release fixes (2026-06)

| Item | Status | Notes |
|------|--------|-------|
| I1 — `pfcore_kernel_hash` + full `lean_environment_hash` | Done | PF-Core `*.lean` bytes + toolchain + lake files |
| I2 — Event sequence order validator | Done | `validate_event_sequence_order`; wired to validate-trace / lean-check |
| I3 — Release bundle CLI | Done | `bundle-release`, `validate-bundle`, manifest hashes |
| I4 — Compositional `certificate_mode` | Done | Six modes; `--certificate-mode` on lean-check; codegen obligations |
| I5 — Resource pattern Lean subset | Done | `ResourceWithinCapabilityPattern` in `ResourcePattern.lean` |
| I6 — Release gates | Done | `pf-core-release-gate.yml`; adapter blocking on main |
| I7 — Single-source catalog | Done | `schemas/pf_core.catalog.json` + `gen_pf_core_catalog.py` + CI drift check |

### Remaining gaps (post Phase I)

- Full global cross-tenant non-interference (covert channels / timing).
- Live CertifyEdge on all developer machines (release gate requires live CLI in CI).
- Rust/TS runtime modules still duplicate some catalog tables until fully wired to `pf_core_catalog.rs` / `pfCoreCatalog.ts` imports.
- WSL/Lean local verification depends on toolchain availability (CI lean job covers release path).

### Honest limitations (Phase F + Tier 2)

- Tenant theorems cover **allowed events in safe traces**, not global cross-tenant non-interference.
- Lean contract discharge maps capability, effect, tenant, decision, event_safe, trace_safe only; role/policy/evidence refs remain runtime-only (`semantics_layer`).
- CertifyEdge live CLI depends on external install; CI uses mock when absent.
- PKI is documented out of scope for v0.1 only.
