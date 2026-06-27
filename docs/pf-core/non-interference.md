# PF-Core conservative non-interference

This document states what PF-Core **proves** about tenant isolation versus what remains **open research**.

## Scope (conservative subset)

PF-Core does **not** claim global non-interference across tenants, covert channels, or arbitrary compositional invariants. The Lean module `lean/PFCore/NonInterference.lean` formalizes a **tenant-scoped trace property** aligned with runtime checks.

### Definitions

| Lean | Meaning |
|------|---------|
| `SameTenant p r` | Alias for `SameTenantResource` — resource tenant equals principal tenant |
| `EventTenantScoped tenant ev` | Principal tenant is `tenant` and all read/write resources match |
| `TraceTenantScoped tenant tr` | Every event in `tr` is `EventTenantScoped tenant` |

Boolean deciders `eventTenantScopedD` and `traceTenantScopedD` mirror these predicates (soundness theorems included).

### Proved theorems (no `sorry`)

| Theorem | Statement |
|---------|-----------|
| `cons_preserves_tenant_scope` | `TraceTenantScoped` preserved under `Trace.cons` when the new event is scoped |
| `eventSafe_allow_implies_tenant_scoped` | Allowed `EventSafe` events are scoped to the principal's tenant |
| `traceSafe_allowed_event_tenant_scoped` | Allowed events in a `TraceSafe` trace are tenant-scoped |
| `traceSafe_implies_tenant_scoped_for_allowed` | Same link, named for documentation |

**Important:** `TraceSafe` does **not** imply `TraceTenantScoped` for denied events. A denied cross-tenant read is `EventSafe` but fails `EventTenantScoped`. Runtime `validate_tenant_isolation` flags such events regardless of decision.

## Runtime alignment

`pcs_core.pf_core_runtime.validate_tenant_isolation(trace)` returns errors when any event's principal tenant mismatches a read/write resource tenant.

Enable via:

```bash
pcs pf-core validate-trace --tenant-isolation examples/pf-core-valid/file_read_allowed/trace.json
```

Invalid fixture: `examples/pf-core-invalid/cross_tenant_leak/`.

## Open (not claimed)

1. Full cross-tenant non-interference (no information flow between tenants).
2. Non-interference under handoff across tenants (handoffs require matching tenants in `HandoffSafe`).
3. Deny-event side channels or resource existence leaks.
4. Compositional preservation of arbitrary user-defined contract invariants beyond the discharged JSON subset.

See also `docs/pf-core/contract-semantics.md` and `docs/pf-core/claim-boundary.md`.
