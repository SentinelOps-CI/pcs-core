import PFCore.Theorems

/-!
# PF-Core conservative tenant-scoped non-interference

This module proves a **conservative subset** of tenant isolation: principals and
resource reads/writes stay within a declared tenant for scoped traces and for
allowed events in safe traces. Full cross-tenant non-interference (e.g. covert
channels, handoff across tenants, or deny-event side effects) is not claimed.
-/

namespace PFCore

/-- Alias for tenant alignment between principal and resource. -/
abbrev SameTenant (p : Principal) (r : Resource) : Prop := SameTenantResource p r

/-- Event `ev` is scoped to `tenant` when the principal and all resources match. -/
def EventTenantScoped (tenant : String) (ev : Event) : Prop :=
  ev.principal.tenant = tenant ∧ ActionWithinTenant ev.principal ev.action

def eventTenantScopedD (tenant : String) (ev : Event) : Bool :=
  decide (ev.principal.tenant = tenant) && actionWithinTenantD ev.principal ev.action

/--
**Meaning:** Event tenant-scoping decider matches principal tenant plus in-tenant resources.

**Trusted use:** Runtime `--tenant-isolation` alignment and conservative isolation claims.

**Does not imply:** Cross-tenant covert channels are absent or deny events are scoped.
-/
theorem eventTenantScopedD_sound (tenant : String) (ev : Event) :
    eventTenantScopedD tenant ev = true ↔ EventTenantScoped tenant ev := by
  cases ev with
  | mk _ p a d =>
    cases d <;>
    simp [eventTenantScopedD, EventTenantScoped, actionWithinTenantD_sound, decide_eq_true_iff]

/-- Every event in trace `tr` stays within `tenant` (principal + resources). -/
def TraceTenantScoped (tenant : String) : Trace → Prop
  | Trace.empty => True
  | Trace.cons tr ev => TraceTenantScoped tenant tr ∧ EventTenantScoped tenant ev

def traceTenantScopedD (tenant : String) (tr : Trace) : Bool :=
  match tr with
  | Trace.empty => true
  | Trace.cons tr' ev => traceTenantScopedD tenant tr' && eventTenantScopedD tenant ev

/--
**Meaning:** Trace tenant-scoping decider reflects inductive tenant scope over events.

**Trusted use:** Whole-trace tenant isolation checks in certificates.

**Does not imply:** Trace hash integrity or completeness of observed runtime events.
-/
theorem traceTenantScopedD_sound (tenant : String) (tr : Trace) :
    traceTenantScopedD tenant tr = true ↔ TraceTenantScoped tenant tr := by
  induction tr with
  | empty => simp [traceTenantScopedD, TraceTenantScoped]
  | cons tr' ev ih =>
    simp [traceTenantScopedD, TraceTenantScoped, eventTenantScopedD_sound, ih, and_left_comm]

/--
**Meaning:** Tenant scope of a trace prefix is preserved when appending a scoped event.

**Trusted use:** Inductive tenant isolation reasoning under `Trace.cons`.

**Does not imply:** The appended event was allowed or safe.
-/
theorem cons_preserves_tenant_scope (tenant : String) (tr : Trace) (ev : Event) :
    TraceTenantScoped tenant tr → EventTenantScoped tenant ev →
    TraceTenantScoped tenant (Trace.cons tr ev) := by
  intro htr hev
  exact ⟨htr, hev⟩

/--
**Meaning:** Allowed safe events place principal and resources within the principal tenant.

**Trusted use:** Linking `EventSafe` to tenant-scoped non-interference for allow decisions.

**Does not imply:** Denied events are tenant-scoped or policy-correct.
-/
theorem eventSafe_allow_implies_tenant_scoped (ev : Event) (h : EventSafe ev)
    (hallow : ev.decision = Decision.allow) :
    EventTenantScoped ev.principal.tenant ev := by
  have hallowed := allowed_event_has_allowed_action ev h hallow
  rcases hallowed with ⟨_, hwithin, _, _⟩
  exact ⟨rfl, hwithin⟩

/--
**Meaning:** Allowed events inside a safe trace are tenant-scoped to the principal tenant.

**Trusted use:** Primary non-interference lemma for certificates over safe traces.

**Does not imply:** Full information-flow non-interference or cross-principal isolation.
-/
theorem traceSafe_allowed_event_tenant_scoped (tr : Trace) (ev : Event)
    (hTrace : TraceSafe tr) (hIn : EventIn ev tr) (hallow : ev.decision = Decision.allow) :
    EventTenantScoped ev.principal.tenant ev :=
  eventSafe_allow_implies_tenant_scoped ev
    (event_in_safe_trace_is_safe tr ev hTrace hIn) hallow

/--
**Meaning:** Alias lemma: safe traces imply tenant scope for allowed member events.

**Trusted use:** Documentation-friendly entry point for tenant isolation claims.

**Does not imply:** Stronger isolation properties beyond `traceSafe_allowed_event_tenant_scoped`.
-/
theorem traceSafe_implies_tenant_scoped_for_allowed (tr : Trace) (ev : Event)
    (hTrace : TraceSafe tr) (hIn : EventIn ev tr) (hallow : ev.decision = Decision.allow) :
    EventTenantScoped ev.principal.tenant ev :=
  traceSafe_allowed_event_tenant_scoped tr ev hTrace hIn hallow

/-- Cross-tenant resource access attempts must be explicitly denied. -/
def CrossTenantDenied (ev : Event) : Prop :=
  ¬ ActionWithinTenant ev.principal ev.action → ev.decision = Decision.deny

/--
**Meaning:** Event is cross-tenant safe when in-tenant or explicitly denied.

**Trusted use:** Conservative global cross-tenant safety over a trace (not full NI).

**Does not imply:** Covert channels, deny-side information leaks, or handoff across tenants.
-/
def EventCrossTenantSafe (ev : Event) : Prop :=
  ActionWithinTenant ev.principal ev.action ∨ ev.decision = Decision.deny

def eventCrossTenantSafeD (ev : Event) : Bool :=
  actionWithinTenantD ev.principal ev.action ||
    match ev.decision with
    | Decision.deny => true
    | Decision.allow => false

/--
**Meaning:** Cross-tenant safety decider matches in-tenant footprint or deny decision.

**Trusted use:** Runtime alignment for cross-tenant denial checks.

**Does not imply:** Policy correctness for deny reasons or resource existence leaks.
-/
theorem eventCrossTenantSafeD_sound (ev : Event) :
    eventCrossTenantSafeD ev = true ↔ EventCrossTenantSafe ev := by
  cases ev with
  | mk _ p a d =>
    cases d <;>
    simp [eventCrossTenantSafeD, EventCrossTenantSafe, actionWithinTenantD_sound, decide_eq_true_iff]

/-- Every event in trace `tr` is in-tenant or cross-tenant denied. -/
def TraceCrossTenantSafe : Trace → Prop
  | Trace.empty => True
  | Trace.cons tr ev => TraceCrossTenantSafe tr ∧ EventCrossTenantSafe ev

def traceCrossTenantSafeD (tr : Trace) : Bool :=
  match tr with
  | Trace.empty => true
  | Trace.cons tr' ev => traceCrossTenantSafeD tr' && eventCrossTenantSafeD ev

/--
**Meaning:** Trace cross-tenant safety decider reflects inductive event property.

**Trusted use:** Whole-trace conservative cross-tenant isolation certificates.

**Does not imply:** Full global non-interference or completeness of observed events.
-/
theorem traceCrossTenantSafeD_sound (tr : Trace) :
    traceCrossTenantSafeD tr = true ↔ TraceCrossTenantSafe tr := by
  induction tr with
  | empty => simp [traceCrossTenantSafeD, TraceCrossTenantSafe]
  | cons tr' ev ih =>
    simp [traceCrossTenantSafeD, TraceCrossTenantSafe, eventCrossTenantSafeD_sound, ih, and_left_comm]

/--
**Meaning:** Cross-tenant denial holds vacuously for in-tenant events.

**Trusted use:** Linking tenant-scoped allows to `CrossTenantDenied`.

**Does not imply:** Cross-tenant allows were correctly denied at runtime.
-/
theorem actionWithinTenant_implies_crossTenantDenied (ev : Event)
    (h : ActionWithinTenant ev.principal ev.action) :
    CrossTenantDenied ev := by
  intro hnot
  exact absurd h hnot

/--
**Meaning:** Allowed safe events are in-tenant, hence cross-tenant denied (vacuously).

**Trusted use:** Building block for `TraceSafe → TraceCrossTenantSafe`.

**Does not imply:** Denied cross-tenant events are safe to emit or side-channel free.
-/
theorem eventSafe_allow_implies_cross_tenant_safe (ev : Event) (h : EventSafe ev)
    (hallow : ev.decision = Decision.allow) :
    EventCrossTenantSafe ev := by
  left
  exact (eventSafe_allow_implies_tenant_scoped ev h hallow).right

/--
**Meaning:** Denied events satisfy cross-tenant safety via explicit deny.

**Trusted use:** Deny branch for trace-level cross-tenant safety.

**Does not imply:** Deny events were tenant-scoped or policy-correct.
-/
theorem event_deny_implies_cross_tenant_safe (ev : Event) (hdeny : ev.decision = Decision.deny) :
    EventCrossTenantSafe ev := by
  right
  exact hdeny

/--
**Meaning:** Safe traces imply conservative cross-tenant safety on every event.

**Trusted use:** Primary link from `TraceSafe` to `TraceCrossTenantSafe` (partial global NI).

**Does not imply:** Full global non-interference, covert channels, or cross-tenant handoff safety.
-/
theorem traceSafe_implies_trace_cross_tenant_safe (tr : Trace) :
    TraceSafe tr → TraceCrossTenantSafe tr := by
  induction tr with
  | empty => intro _; trivial
  | cons tr' ev ih =>
    intro h
    rcases h with ⟨hTrSafe, hEvSafe⟩
    refine ⟨ih hTrSafe, ?_⟩
    cases hdec : ev.decision with
    | allow =>
      exact eventSafe_allow_implies_cross_tenant_safe ev hEvSafe hdec
    | deny =>
      exact event_deny_implies_cross_tenant_safe ev hdec

/--
**Meaning:** Alias: `TraceSafe` yields `TraceCrossTenantSafe` under PF-Core event safety.

**Trusted use:** Documentation entry point; not a claim of full global NI.

**Does not imply:** Stronger isolation than `traceSafe_implies_trace_cross_tenant_safe`.
-/
theorem traceSafe_implies_cross_tenant_safe (tr : Trace) :
    TraceSafe tr → TraceCrossTenantSafe tr :=
  traceSafe_implies_trace_cross_tenant_safe tr

/-- No allowed event reads or writes resources outside the principal tenant. -/
def EventTenantIsolated (ev : Event) : Prop :=
  ev.decision = Decision.allow → ActionWithinTenant ev.principal ev.action

def eventTenantIsolatedD (ev : Event) : Bool :=
  match ev.decision with
  | Decision.deny => true
  | Decision.allow => actionWithinTenantD ev.principal ev.action

/--
**Meaning:** Tenant isolation decider for allowed events matches in-tenant footprint.

**Trusted use:** Runtime `--tenant-isolation` alignment for allowed events.

**Does not imply:** Denied cross-tenant attempts are safe or side-channel free.
-/
theorem eventTenantIsolatedD_sound (ev : Event) :
    eventTenantIsolatedD ev = true ↔ EventTenantIsolated ev := by
  cases ev with
  | mk _ p a d =>
    cases d <;> simp [eventTenantIsolatedD, EventTenantIsolated, actionWithinTenantD_sound,
      decide_eq_true_iff]

/-- Trace satisfies tenant isolation: allowed events stay within principal tenant resources. -/
def TenantIsolation : Trace → Prop
  | Trace.empty => True
  | Trace.cons tr ev => TenantIsolation tr ∧ EventTenantIsolated ev

def tenantIsolationD (tr : Trace) : Bool :=
  match tr with
  | Trace.empty => true
  | Trace.cons tr' ev => tenantIsolationD tr' && eventTenantIsolatedD ev

/--
**Meaning:** Trace tenant-isolation decider reflects inductive `TenantIsolation`.

**Trusted use:** Whole-trace tenant isolation certificates.

**Does not imply:** Covert channels, timing leaks, or cross-tenant handoff safety.
-/
theorem tenantIsolationD_sound (tr : Trace) :
    tenantIsolationD tr = true ↔ TenantIsolation tr := by
  induction tr with
  | empty => simp [tenantIsolationD, TenantIsolation]
  | cons tr' ev ih =>
    simp [tenantIsolationD, TenantIsolation, eventTenantIsolatedD_sound, ih, and_left_comm]

/--
**Meaning:** Allowed safe events are tenant-isolated.

**Trusted use:** Building block for `TraceSafe → TenantIsolation`.

**Does not imply:** Denied events were tenant-scoped.
-/
theorem eventSafe_allow_implies_tenant_isolated (ev : Event) (h : EventSafe ev)
    (hallow : ev.decision = Decision.allow) :
    EventTenantIsolated ev := by
  intro _
  exact (eventSafe_allow_implies_tenant_scoped ev h hallow).right

/--
**Meaning:** `TraceSafe` implies tenant isolation on allowed events (strongest PF-Core NI lemma).

**Trusted use:** Primary tenant isolation entry point from trace safety.

**Does not imply:** Full information-flow non-interference, covert channels, timing, or deny-event scope.
-/
theorem traceSafe_implies_tenant_isolation (tr : Trace) :
    TraceSafe tr → TenantIsolation tr := by
  induction tr with
  | empty => intro _; trivial
  | cons tr' ev ih =>
    intro h
    rcases h with ⟨hTrSafe, hEvSafe⟩
    refine ⟨ih hTrSafe, ?_⟩
    intro hallow
    exact eventSafe_allow_implies_tenant_isolated ev hEvSafe hallow

/--
**Meaning:** Under explicit admissibility on every allowed event, trace safety yields tenant isolation.

**Trusted use:** Alternative statement when `ActionAdmissible` is assumed per allow event.

**Does not imply:** Stronger isolation without the admissibility hypothesis.
-/
theorem traceSafe_implies_tenant_isolation_admissible (tr : Trace) :
    TraceSafe tr →
    (∀ ev, EventIn ev tr → ev.decision = Decision.allow → ActionAdmissible ev.principal ev.action) →
    TenantIsolation tr := by
  intro h _ 
  exact traceSafe_implies_tenant_isolation tr h

end PFCore

