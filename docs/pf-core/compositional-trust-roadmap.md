# PF-Core compositional trust roadmap

Extend PF-Core from per-trace concrete proofs to compositional theorems that preserve trace safety under controlled extension (new events, delegated authority, contract refinement) without re-running full Lean codegen for every composition step.

## Theorem targets

| Theorem | Intent | Status |
|---------|--------|--------|
| `safe_extension_preserves_trace_safe` | Appending an `EventSafe` event to a `TraceSafe` trace yields `TraceSafe` | **Proved** (`lean/PFCore/Compositional.lean`; alias of `trace_safe_invariant_preserved_cons`) |
| `handoff_composition_does_not_expand_authority` | Chained `HandoffSafe` records do not expand authority beyond the first source when the second hop stays within the first delegation envelope | **Proved** (`lean/PFCore/Compositional.lean`) |
| `contract_invariant_preserved_by_safe_extension` | Trace-safe contract invariant preserved under `EventSafe` extension | **Proved** (`lean/PFCore/Compositional.lean`) |
| `composed_contract_preserves_component_invariants` | `Contract.seq` invariant splits/joins component invariants | **Proved** (`lean/PFCore/Compositional.lean`) |
| `handoff_preserves_trace_safe` | `HandoffSafe` delegation with minimal state model preserves `TraceSafe` and bounded authority | **Proved** (`lean/PFCore/State.lean`; minimal state, not full operational semantics) |
| `contract_refinement_preserves_trace_safe` | Stricter contract discharge on a sub-trace preserves global trace safety | **Proved** (`lean/PFCore/Compositional.lean`) |
| `replay_preserves_claim_boundary` | Hash replay match implies no silent claim-class upgrade | **Operational** (`python/pcs_core/pf_core_replay.py`; Python theorem + tests) |
| `certificate_binds_generated_model` | Certificate hashes uniquely bind JSON to generated Lean model | **Operational** (`pcs pf-core verify-proof-binding`) |

## Dependencies

- Stable `PFCoreTraceClaimClass` vs `PFCoreCertificateClaimClass` separation (implemented)
- Closed direct-trace effect catalog and capability/effect alignment (implemented)
- `proof_term_hash` binding on `LeanKernelChecked` certificates (implemented)
- Full semantic validation in `pcs pf-core lean-check` (implemented)

## Out of scope for this roadmap phase

- Full global non-interference across tenants — **Partial**: `TenantIsolation` + `TraceCrossTenantSafe` + `TenantProjectionIsolation`; paired-execution NI / covert channels / timing not claimed ([non-interference.md](non-interference.md), [runtime-semantics.md](runtime-semantics.md))
- Full JSON contract field encoding in Lean — **Partial**: `require_role` lean discharge; policy/evidence refs runtime-only

See [non-interference.md](non-interference.md) and [assumptions.md](assumptions.md) for current deferrals.

## RoleMap (minimal kernel)

| Item | Status |
|------|--------|
| `RoleMap` structure + `expandPrincipal` | **Proved** (`lean/PFCore/RoleMap.lean`) |
| `aligned_role_capability_granted` | **Proved** (aligned principals → `HasCapability`) |
| Full runtime `ROLE_CAPABILITY_MAP` parity in Lean | **Proved** (`runtimeRoleMap` + `runtime_role_expansion_subset`; key/cap parity tests in `test_pf_core_research.py`) |
| `require_role` lean discharge | **Partial** | `ContractDecide.requireRole` + codegen when `semantics_layer.require_role = lean` |

## Research-grade extensions (Phases I–IV)

| Theorem | Intent | Status |
|---------|--------|--------|
| `stepState_frame_preserved` | Operational allow steps preserve frame invariants | **Proved** (`Transition.lean`) |
| `traceExtendsSafely_of_step` | Successful step links to safe trace extension | **Proved** (`Transition.lean`) |
| `safe_extension_preserves_trace_safe_strong` | Safe extension + frames → `TraceSafe (Trace.cons tr ev)` | **Proved** (`Transition.lean`) |
| `effect_frame_prevents_undeclared_writes` | Write-free effect frame → no writes on `R` (with footprint alignment) | **Proved** (`EffectFrame.lean`) |
| `handoff_preserves_trace_safe_strong` | Handoff + frames + trace safety | **Proved** (`State.lean`) |
| `handoff_composition_global` | Multi-hop handoff authority bounded by first source | **Proved** (`Compositional.lean`) |
| `traceSafe_implies_tenant_isolation` | Allowed events in safe traces stay tenant-scoped | **Proved** (`NonInterference.lean`) |
| `traceSafe_implies_low_events_tenant_scoped` | Low-projected events in safe traces are tenant-scoped | **Proved** (`Observational.lean`; not paired-execution NI) |
| `traceSafe_implies_tenant_projection_isolation` | Single-trace observational isolation | **Proved** (`Observational.lean`; user-facing name for prior observational NI) |
| `accepted_transition_no_undeclared_sensitive_observation` | Observed sensitive effects stay in declared frame under instrumentation | **Proved** (`ObservedEffect.lean`; assumes `TrustedInstrumentation`) |
| `eventSafeDenyClosed_implies_eventSafe` | Deny-closed refinement of `EventSafe` | **Proved** (`DenyClosed.lean`) |
| `PairedExecutionNonInterference` | Paired executions + scheduler + timing | **Scaffolding only** (`PairedExecution.lean`; not proved) |
