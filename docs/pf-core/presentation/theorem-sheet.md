# PF-Core theorem sheet

Exact statements from `lean/PFCore/` trusted modules.

## Public certificate-mode claim surface

Public posture is governed by [`schemas/pf_core.certificate_mode_status.json`](../../../schemas/pf_core.certificate_mode_status.json):

| Mode | Status |
|------|--------|
| `TraceSafeRCertificate` | `release_candidate` (sole tool-use RC) |
| `TraceSafeCertificate` | `legacy` |
| `HandoffSafeCertificate`, `ContractCheckedCertificate`, `EffectFrameCertificate`, `FramePreservedCertificate` | `disabled` |
| `CompositionalExtensionCertificate` | `experimental` (A6 `CompositionalSafeExtension`; not RC) |
| External `CertificateChecked` | `preview` |

Scaffolded only (not public issuance): `TracePrefixSafeCertificate` (prefix-only), `DenyClosedCertificate` (disabled — insufficient runtime evidence).

Disabled modes are not public issuance claims. Theorems below remain in the kernel; specialized certificates stay disabled for public RC (evidence repaired for handoff/contract/effect-frame/transitions; enablement deferred). Issuable via `--allow-non-public-modes` for tests.

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

## Conservative tenant projection isolation (`lean/PFCore/Observational.lean`)

User-facing name: **`TenantProjectionIsolation`** (Lean `NonInterference` is a compatibility alias only; paired-execution NI is unproved scaffolding in `PairedExecution.lean`).

### `traceSafe_implies_tenant_projection_isolation`

```lean
theorem traceSafe_implies_tenant_projection_isolation
    (tenantLow tenantHigh : String) (tr : Trace) (hTrace : TraceSafe tr) :
    TenantProjectionIsolation tenantLow tenantHigh tr
```

## Conservative tenant isolation (`lean/PFCore/NonInterference.lean`)

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

## Compositional trust (`lean/PFCore/Compositional.lean`)

### `CompositionalSafeExtension` (A6)

Safe prefix + `EventSafe` + successful `Applies` + preserved `FrameValid` frames.

```lean
def CompositionalSafeExtension (tr : Trace) (ev : Event) (s s' : State) : Prop :=
  TraceSafe tr ∧ EventSafe ev ∧ Applies ev s s' ∧ FrameValid s ∧ FrameValid s'

theorem compositional_safe_extension_yields_safe_extended_trace
    (tr : Trace) (ev : Event) (s s' : State)
    (h : CompositionalSafeExtension tr ev s s') :
    TraceSafe (Trace.cons tr ev)
```

Prefix-only chaining is `TracePrefixSafe` (alias of `TraceSafe`); experimental certificate alias `TracePrefixSafeCertificate`.

### `safe_extension_preserves_trace_safe`

Appending an `EventSafe` event to a `TraceSafe` trace yields `TraceSafe`.

```lean
theorem safe_extension_preserves_trace_safe (tr : Trace) (ev : Event) :
    TraceSafe tr → EventSafe ev → TraceSafe (Trace.cons tr ev)
```

### `handoff_composition_does_not_expand_authority`

Chained handoffs do not expand authority beyond the first source when the second hop delegates only capabilities from the first hop.

```lean
theorem handoff_composition_does_not_expand_authority (h1 h2 : Handoff) (cap : String) :
    HandoffSafe h1 → HandoffSafe h2 → HandoffChain h1 h2 →
    CapabilitySubset h2.delegatedCapabilities h1.delegatedCapabilities →
    cap ∈ h2.delegatedCapabilities → HasCapability h1.fromPrincipal cap
```

### `composed_contract_preserves_component_invariants`

Sequential contract invariant joins component invariants.

```lean
theorem composed_contract_preserves_component_invariants (c1 c2 : Contract) (tr : Trace) :
    c1.invariant tr → c2.invariant tr → (Contract.seq c1 c2).invariant tr
```

## RoleMap (`lean/PFCore/RoleMap.lean`)

### `aligned_role_capability_granted`

Aligned principals hold capabilities contributed by mapped roles.

```lean
theorem aligned_role_capability_granted (rm : RoleMap) (p : Principal) (role cap : String) :
    PrincipalCapabilitiesAligned rm p → role ∈ p.roles → cap ∈ rm.lookup role →
    HasCapability p cap
```

### `runtime_role_expansion_subset`

Role expansion yields only capability ids listed in the static runtime map union.

```lean
theorem runtime_role_expansion_subset (roles : List String) (cap : String) :
    cap ∈ runtimeRoleMap.expandRoles roles → cap ∈ runtimeRoleMap.allMappedCapabilities
```

## Minimal state + handoff trace safety (`lean/PFCore/State.lean`)

### `handoff_preserves_trace_safe`

Conservative link: safe trace extension plus bounded delegation authority (minimal state model).

```lean
theorem handoff_preserves_trace_safe (tr : Trace) (s : State) (h : Handoff) (ev : Event) :
    TraceSafe tr → HandoffSafe h → EventSafe ev →
    TraceSafe (Trace.cons tr ev) ∧
    (∀ cap ∈ h.delegatedCapabilities, HasCapability h.fromPrincipal cap) ∧
    (∀ cap ∈ (HandoffApplies h (applyEvent s ev)).capabilities,
      HasCapability h.fromPrincipal cap ∨ HasCapability h.toPrincipal cap)
```

## Cross-tenant safety (`lean/PFCore/NonInterference.lean`)

### `traceSafe_implies_trace_cross_tenant_safe`

`TraceSafe` implies conservative cross-tenant safety (not full global NI).

```lean
theorem traceSafe_implies_trace_cross_tenant_safe (tr : Trace) :
    TraceSafe tr → TraceCrossTenantSafe tr
```

## Operational state + transitions (`lean/PFCore/Transition.lean`)

### `stepState_frame_preserved`

Allowed operational steps preserve resource/capability frame invariants.

```lean
theorem stepState_frame_preserved (s s' : State) (ev : Event) (hApply : Applies ev s s') :
    FrameValid s → FrameValid s'
```

### `safe_extension_preserves_trace_safe_strong`

Safe extension with operational linkage yields `TraceSafe` on `Trace.cons`.

```lean
theorem safe_extension_preserves_trace_safe_strong (tr : Trace) (ev : Event)
    (s s' : State) (hExt : TraceExtendsSafely tr ev) (hApply : Applies ev s s')
    (_hFrame : FrameValid s → FrameValid s') :
    TraceSafe (Trace.cons tr ev)
```

## Effect frames (`lean/PFCore/EffectFrame.lean`)

Certificate mode `EffectFrameCertificate` (disabled for public RC; `--allow-non-public-modes`
for fixtures) binds an independently declared `PFCoreEffectFrame.v0` artifact. Generated
proofs discharge `actionEffectsInFrameD concreteAction concreteDeclaredFrame = true` where
`concreteDeclaredFrame` is emitted from the frame artifact (not `action.effects`). v0 policy:
one global frame per multi-event trace.

### `effect_frame_prevents_undeclared_writes`

Write-free effect frame prevents writes on resource `R` when write footprint requires write effect.

```lean
theorem effect_frame_prevents_undeclared_writes (a : Action) (frame : List Effect) (r : Resource) :
    ActionEffectsInFrame a frame → Effect.write ∉ frame → WriteFootprintRequiresWriteEffect a →
    r ∉ a.writes
```

## Contract refinement (`lean/PFCore/Compositional.lean`)

### `contract_refinement_preserves_trace_safe`

```lean
theorem contract_refinement_preserves_trace_safe (cStrong cWeak : Contract) (tr : Trace) :
    TraceSatisfiesContract cStrong tr → ContractRefinement cStrong cWeak →
    TraceSatisfiesContract cWeak tr
```

## Tenant isolation (`lean/PFCore/NonInterference.lean`)

### `traceSafe_implies_tenant_isolation`

```lean
theorem traceSafe_implies_tenant_isolation (tr : Trace) :
    TraceSafe tr → TenantIsolation tr
```

**Does not imply:** Covert channels, timing leaks, or deny-event tenant scope.
