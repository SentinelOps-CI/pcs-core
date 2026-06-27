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
  rcases hallowed with ⟨_, hwithin⟩
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

end PFCore
