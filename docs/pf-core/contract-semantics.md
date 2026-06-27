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

## semantics_layer (PFCoreContract.v0)

Each contract may declare which fields are discharged in Lean, checked only at runtime, or explicitly out of scope:

```json
"semantics_layer": {
  "require_capability": "lean",
  "require_role": "runtime",
  "require_decision": "lean",
  "require_trace_safe": "lean"
}
```

Field names are bare (unique across pre/post/invariant). When `semantics_layer` is omitted, defaults are derived from the mapping table below.

| Layer | Meaning |
|-------|---------|
| `lean` | Discharged by generated Lean `ContractDecide` proofs when lean-check runs |
| `runtime` | Validated by `pcs pf-core validate-contracts` only |
| `out_of_scope` | Documented gap; must not appear on active required fields |

Validation rejects orphan semantics entries, active fields marked `out_of_scope`, and inconsistent explicit layers.

## semantics_layer (PFCoreContract.v0)

Contracts may declare per-field discharge layers at the source:

```json
"semantics_layer": {
  "require_capability": "lean",
  "require_role": "runtime",
  "require_policy_ref": "runtime"
}
```

Allowed values: `lean`, `runtime`, `out_of_scope`.

When `semantics_layer` is omitted, defaults are derived from the mapping table below. Explicit entries must match the canonical layer for active fields (validated by `pcs validate`).

## Formal mapping table (JSON ↔ Lean ↔ runtime)

| JSON field | Default layer | Runtime (`pf_core_contract.py`) | Lean decider | Generated proof |
|------------|---------------|-----------------------------------|--------------|-----------------|
| `pre.require_capability` | `lean` | `_principal_has_capability` | `contractPreD` / `hasCapabilityD` | `concrete_contract_pre_*` |
| `pre.require_effect` | `lean` | `_action_has_effect` | `contractPreD` / `actionHasEffectD` | `concrete_contract_pre_*` |
| `pre.require_tenant_match` | `lean` | `_tenant_matches` | `contractPreD` / `actionWithinTenantD` | `concrete_contract_pre_*` |
| `pre.require_role` | `runtime` | role list membership | **Not mapped** | — |
| `pre.require_policy_ref` | `runtime` | `contract_refs` contains ref | **Not mapped** | — |
| `pre.require_evidence_ref` | `runtime` | `evidence_refs` contains ref | **Not mapped** | — |
| `post.require_decision` | `lean` | decision equality | `contractPostD` | `concrete_contract_post_*` |
| `post.require_event_safe` | `lean` | capability + tenant on allow | `contractPostD` / `eventSafeD` | `concrete_contract_post_*` |
| `invariant.require_trace_safe` | `lean` | (trace-level) | `contractInvariantD` / `traceSafeD` | `concrete_trace_satisfies_*` |

Per-event discharge: `satisfiesContractSpecD`. Trace-level: `traceSatisfiesContractSpecsD`.

## Lean codegen pipeline

When `contract_refs` appear on events and contract JSON is found alongside the trace:

1. `pcs pf-core validate-contracts` (runtime) — required before `lean-check` succeeds.
2. Generated `.lean` file includes `ContractPreSpec` / `PostSpec` / `Inv` defs and `decide` proofs.
3. `lake env lean` on the generated module discharges concrete obligations.

Fields marked **Not mapped** remain runtime-only unless `semantics_layer` overrides a mapped field to `runtime`. Codegen skips Lean obligations for non-`lean` fields.

## contract_semantics_checked (PFCoreCertificate.v0)

When `pcs pf-core lean-check` emits a certificate, it includes:

```json
"contract_semantics_checked": {
  "lean": ["contract-id.pre.require_capability", "..."],
  "runtime": ["contract-id.pre.require_role", "..."]
}
```

- `lean`: contract fields with `semantics_layer` `lean` (discharged by generated Lean proofs when lean-check succeeds).
- `runtime`: fields with layer `runtime` (validated by `pcs pf-core validate-contracts`).

Out-of-scope fields are omitted from both lists.

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
