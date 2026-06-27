# PF-Core conservative non-interference

This document states what PF-Core **proves** about tenant isolation versus what remains **open research**.

## Scope (conservative subset)

PF-Core does **not** claim global non-interference across tenants, covert channels, or arbitrary compositional invariants. The Lean module `lean/PFCore/NonInterference.lean` formalizes **conservative tenant isolation for allowed events** aligned with runtime checks.

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

### Conservative cross-tenant safety (partial global NI)

| Lean | Meaning |
|------|---------|
| `CrossTenantDenied ev` | Cross-tenant resource access implies `Decision.deny` |
| `EventCrossTenantSafe ev` | In-tenant footprint or explicit deny |
| `TraceCrossTenantSafe tr` | Every event is `EventCrossTenantSafe` |

| Theorem | Statement |
|---------|-----------|
| `traceSafe_implies_trace_cross_tenant_safe` | `TraceSafe tr → TraceCrossTenantSafe tr` |
| `traceSafe_implies_cross_tenant_safe` | Alias of the above |

**Important:** This is **not** full global non-interference. Covert channels, deny-side leaks, cross-tenant handoffs, and scheduler-level information flow remain open.

**Important:** `TraceSafe` does **not** imply `TraceTenantScoped` for denied events. A denied cross-tenant read is `EventSafe` but fails `EventTenantScoped`. Runtime `validate_tenant_isolation` flags such events regardless of decision.

## Runtime alignment

`pcs_core.pf_core_runtime.validate_tenant_isolation(trace)` returns errors when any event's principal tenant mismatches a read/write resource tenant.

Enable via:

```bash
pcs pf-core validate-trace --tenant-isolation examples/pf-core-valid/file_read_allowed/trace.json
```

Invalid fixture: `examples/pf-core-invalid/cross_tenant_leak/`.

## RoleMap permanent assumption

Lean `HasCapability` inspects `principal.capabilities` only; **roles are not expanded in the kernel** during proof discharge. The runtime compiler applies `ROLE_CAPABILITY_MAP` in `pf_core_runtime.py` when compiling observations. Lean `runtimeRoleMap` in `RoleMap.lean` mirrors the same keys for parity audits; codegen still emits explicit expanded capabilities on principals. Role-to-capability expansion at lean-check time remains a **trusted-boundary assumption** unless principals are proven aligned via `PrincipalCapabilitiesAligned`.

## Open (not claimed — full global NI deferred)

1. **Full global cross-tenant non-interference** (information-flow between tenants under arbitrary schedulers and adversaries). `traceSafe_implies_trace_cross_tenant_safe` covers in-tenant allows and explicit denies only.
2. Non-interference under handoff across tenants (handoffs require matching tenants in `HandoffSafe`).
3. Deny-event side channels or resource existence leaks.
4. Compositional preservation of arbitrary user-defined contract invariants beyond the discharged JSON subset.

See also `docs/pf-core/contract-semantics.md` and `docs/pf-core/claim-boundary.md`.
