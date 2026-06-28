# PF-Core conservative non-interference

This document states what PF-Core **proves** about tenant isolation versus what remains **open research**.

## Scope (conservative subset)

PF-Core does **not** claim global non-interference across tenants, covert channels, or arbitrary compositional invariants. The Lean modules `lean/PFCore/NonInterference.lean` and `lean/PFCore/Observational.lean` formalize **conservative tenant isolation and observational projection** aligned with runtime checks.

**Observational equivalence does not imply covert channels are absent.** Two traces may agree on low projections while differing on denied events, cross-tenant attempts, timing, or side channels not recorded in PF-Core events.

### Observational vocabulary (`Observational.lean`)

| Lean | Meaning |
|------|---------|
| `LowEvent tenant ev` | Allowed event whose principal tenant equals `tenant` |
| `HighEvent tenant ev` | Not low-visible to observer `tenant` (denied, other tenant, etc.) |
| `HighTenantEvent tenantHigh ev` | Event whose principal tenant equals `tenantHigh` |
| `TraceProjection tenant tr` | Oldest-first list of low events in `tr` |
| `ObservationallyEquivalentForTenant t tr1 tr2` | Equal low projections: `TraceProjection t tr1 = TraceProjection t tr2` |
| `NonInterference tenantLow tenantHigh tr` | Conservative trace-level NI: low projection contains only `LowEvent tenantLow`; high-tenant events are `HighEvent tenantLow` (vacuous when tenants equal) |

| Theorem | Statement |
|---------|-----------|
| `traceSafe_implies_low_events_tenant_scoped` | Every low-projected event in a `TraceSafe` trace is `EventTenantScoped tenant` |
| `non_interference_definitional` | Distinct tenants: high-tenant events never appear in low projection |
| `traceSafe_implies_non_interference` | `TraceSafe tr → NonInterference tenantLow tenantHigh tr` |
| `tenantIsolation_implies_non_interference` | `TenantIsolation tr` yields NI for distinct tenants |
| `traceCrossTenantSafe_implies_high_tenant_not_low` | High-tenant events are high-sensitive for a distinct low observer |
| `non_interference_observational_equivalence` | Matching low projections imply observational equivalence |

This is **not** full non-interference: high events, deny-side leaks, scheduler-level indistinguishability, **covert channels**, **timing leaks**, and **handoff across tenants** remain open.

### Tenant isolation vocabulary (`NonInterference.lean`)

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

1. **Full global cross-tenant non-interference** (information-flow between tenants under arbitrary schedulers and adversaries). `traceSafe_implies_trace_cross_tenant_safe` and `NonInterference` cover projection-based low/high separation only.
2. **Covert channels** not recorded as PF-Core events (timing, resource existence, side channels on deny paths).
3. **Timing leaks** and scheduler-level indistinguishability.
4. Non-interference under **handoff across tenants** (handoffs require matching tenants in `HandoffSafe`).
5. Deny-event side channels or resource existence leaks.
6. Compositional preservation of arbitrary user-defined contract invariants beyond the discharged JSON subset.
7. Cross-trace NI: replacing high-tenant events in a trace while preserving low projection (system-level property, not proved for arbitrary schedulers).

See also `docs/pf-core/contract-semantics.md` and `docs/pf-core/claim-boundary.md`.
