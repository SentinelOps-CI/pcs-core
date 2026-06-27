# PF-Core theorem sheet

Exact statements from `lean/PFCore/` trusted modules.

## Trace safety (`lean/PFCore/Theorems.lean`)

### `allowed_event_has_allowed_action`

From `EventSafe`, an allowed decision implies the action was allowed.

```lean
theorem allowed_event_has_allowed_action (ev : Event) (h : EventSafe ev) (hallow : ev.decision = Decision.allow) :
    ActionAllowed ev.principal ev.action
```

### `event_in_safe_trace_is_safe`

Every event in a safe trace is itself safe.

```lean
theorem event_in_safe_trace_is_safe (tr : Trace) (ev : Event)
    (hTrace : TraceSafe tr) (hIn : EventIn ev tr) : EventSafe ev
```

### `every_allowed_event_in_safe_trace_is_allowed`

Any allowed event inside a safe trace corresponds to an allowed action.

```lean
theorem every_allowed_event_in_safe_trace_is_allowed (tr : Trace) (ev : Event)
    (hTrace : TraceSafe tr) (hIn : EventIn ev tr) (hallow : ev.decision = Decision.allow) :
    ActionAllowed ev.principal ev.action
```

## Conservative non-interference (`lean/PFCore/NonInterference.lean`)

### `cons_preserves_tenant_scope`

Tenant scope preserved under `Trace.cons`.

```lean
theorem cons_preserves_tenant_scope (tenant : String) (tr : Trace) (ev : Event) :
    TraceTenantScoped tenant tr → EventTenantScoped tenant ev →
    TraceTenantScoped tenant (Trace.cons tr ev)
```

### `traceSafe_allowed_event_tenant_scoped`

Allowed events in a safe trace are tenant-scoped (does **not** claim global non-interference).

```lean
theorem traceSafe_allowed_event_tenant_scoped (tr : Trace) (ev : Event)
    (hTrace : TraceSafe tr) (hIn : EventIn ev tr) (hallow : ev.decision = Decision.allow) :
    EventTenantScoped ev.principal.tenant ev
```

## Contract deciders (`lean/PFCore/ContractDecide.lean`)

### `contractPreD_sound`

```lean
theorem contractPreD_sound (spec : ContractPreSpec) (p : Principal) (a : Action) :
    contractPreD spec p a = true ↔ ContractPreHolds spec p a
```

### `satisfiesContractSpecD_sound`

```lean
theorem satisfiesContractSpecD_sound (pre : ContractPreSpec) (post : ContractPostSpec) (ev : Event) :
    satisfiesContractSpecD pre post ev = true ↔ SatisfiesContractSpec pre post ev
```

### `traceSatisfiesContractSpecsD_sound`

```lean
theorem traceSatisfiesContractSpecsD_sound (pre : ContractPreSpec) (post : ContractPostSpec)
    (inv : ContractInvariantSpec) (tr : Trace) :
    traceSatisfiesContractSpecsD pre post inv tr = true ↔
      TraceSatisfiesContractSpecs pre post inv tr
```

## Handoff safety (`lean/PFCore/Handoff.lean`)

### `handoffSafeD_sound`

Boolean decider for non-expanding delegation.

```lean
theorem handoffSafeD_sound (h : Handoff) :
    handoffSafeD h = true ↔ HandoffSafe h
```

### `handoff_does_not_expand_authority`

Safe handoff never grants a capability absent from the source principal.

```lean
theorem handoff_does_not_expand_authority (h : Handoff) (cap : String) :
    HandoffSafe h → cap ∈ h.delegatedCapabilities → HasCapability h.fromPrincipal cap
```

## Decider alignment (runtime)

Python deciders in `lean_check.py` mirror:

- `eventSafeD` — deny is always safe; allow requires capability + tenant + resource scope
- `traceSafeD` — all events safe
- `handoffSafeD` — delegated capabilities subset of source (via `validate_handoff_authority`)
- `validate_tenant_isolation` — conservative mirror of `EventTenantScoped` / `TraceTenantScoped`

`LeanKernelChecked` is emitted only when a generated concrete proof evaluates `traceSafeD tr = true` in the Lean kernel (plus contract deciders when `contract_refs` are discharged).

`CertificateChecked` is emitted only via CertifyEdge or `attach-certificate-check`; it never upgrades to `LeanKernelChecked`.
