# PF-Core contract semantics

This document maps `PFCoreContract.v0` JSON fields to runtime checker predicates, Lean `ContractDecide` deciders, and generated proof obligations.

## Lean structures

| Module | Role |
|--------|------|
| `lean/PFCore/Contract.lean` | Prop-level `Contract`, `SatisfiesContract`, sequential composition |
| `lean/PFCore/ContractDecide.lean` | Decidable JSON contract specs + soundness theorems |

### ContractDecide specs

| Lean structure | JSON source |
|----------------|-------------|
| `ContractPreSpec` | `pre` object |
| `ContractPostSpec` | `post` object |
| `ContractInvariantSpec` | `invariant` object |

## Formal mapping table (JSON ↔ Lean ↔ runtime)

| JSON field | Runtime (`pf_core_contract.py`) | Lean decider | Generated proof |
|------------|-----------------------------------|--------------|-----------------|
| `pre.require_capability` | `_principal_has_capability` | `contractPreD` / `hasCapabilityD` | `concrete_contract_pre_*` |
| `pre.require_effect` | `_action_has_effect` | `contractPreD` / `actionHasEffectD` | `concrete_contract_pre_*` |
| `pre.require_tenant_match` | `_tenant_matches` | `contractPreD` / `actionWithinTenantD` | `concrete_contract_pre_*` |
| `pre.require_role` | role list membership | **Not mapped** | — |
| `pre.require_policy_ref` | `contract_refs` contains ref | **Not mapped** | — |
| `pre.require_evidence_ref` | `evidence_refs` contains ref | **Not mapped** | — |
| `post.require_decision` | decision equality | `contractPostD` | `concrete_contract_post_*` |
| `post.require_event_safe` | capability + tenant on allow | `contractPostD` / `eventSafeD` | `concrete_contract_post_*` |
| `invariant.require_trace_safe` | (trace-level) | `contractInvariantD` / `traceSafeD` | `concrete_trace_satisfies_*` |

Per-event discharge: `satisfiesContractSpecD`. Trace-level: `traceSatisfiesContractSpecsD`.

## Lean codegen pipeline

When `contract_refs` appear on events and contract JSON is found alongside the trace:

1. `pcs pf-core validate-contracts` (runtime) — required before `lean-check` succeeds.
2. Generated `.lean` file includes `ContractPreSpec` / `PostSpec` / `Inv` defs and `decide` proofs.
3. `lake env lean` on the generated module discharges concrete obligations.

Fields marked **Not mapped** remain runtime-only; codegen documents the gap in the header when refs exist but contracts are missing.

## Invariant preservation (Lean)

The canonical trace-safety invariant is `TraceSafe`. Lean proves conservative preservation:

```lean
theorem trace_safe_invariant_preserved_cons (tr : Trace) (ev : Event) :
    TraceSafe tr → EventSafe ev → TraceSafe (Trace.cons tr ev)
```

Arbitrary user-defined `Contract.invariant` functions are not automatically preserved under `cons` without additional structure.

## When to use which checker

| Goal | Command |
|------|---------|
| JSON contract pre/post on events | `pcs pf-core validate-contracts` |
| Hash chain + EventSafe deciders | `pcs pf-core validate-trace` |
| Tenant isolation (conservative) | `pcs pf-core validate-trace --tenant-isolation` |
| Kernel proof of trace/event + contract deciders | `pcs pf-core lean-check --trace …` |
| External temporal/property checker | `pcs pf-core certifyedge-check --trace … --property …` |

See `docs/pf-core/non-interference.md` for tenant-scoped non-interference claims.
