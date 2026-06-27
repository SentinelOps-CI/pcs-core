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

theorem traceTenantScopedD_sound (tenant : String) (tr : Trace) :
    traceTenantScopedD tenant tr = true ↔ TraceTenantScoped tenant tr := by
  induction tr with
  | empty => simp [traceTenantScopedD, TraceTenantScoped]
  | cons tr' ev ih =>
    simp [traceTenantScopedD, TraceTenantScoped, eventTenantScopedD_sound, ih, and_left_comm]

/-- Tenant scope is preserved under `Trace.cons` when the new event is scoped. -/
theorem cons_preserves_tenant_scope (tenant : String) (tr : Trace) (ev : Event) :
    TraceTenantScoped tenant tr → EventTenantScoped tenant ev →
    TraceTenantScoped tenant (Trace.cons tr ev) := by
  intro htr hev
  exact ⟨htr, hev⟩

/-- Allowed safe events are tenant-scoped to the principal's tenant. -/
theorem eventSafe_allow_implies_tenant_scoped (ev : Event) (h : EventSafe ev)
    (hallow : ev.decision = Decision.allow) :
    EventTenantScoped ev.principal.tenant ev := by
  have hallowed := allowed_event_has_allowed_action ev h hallow
  rcases hallowed with ⟨_, hwithin⟩
  exact ⟨rfl, hwithin⟩

/-- Allowed events inside a safe trace are tenant-scoped (conservative non-interference link). -/
theorem traceSafe_allowed_event_tenant_scoped (tr : Trace) (ev : Event)
    (hTrace : TraceSafe tr) (hIn : EventIn ev tr) (hallow : ev.decision = Decision.allow) :
    EventTenantScoped ev.principal.tenant ev :=
  eventSafe_allow_implies_tenant_scoped ev
    (event_in_safe_trace_is_safe tr ev hTrace hIn) hallow

/-- When a trace is tenant-scoped and safe, every allowed event stays within its principal tenant. -/
theorem traceSafe_implies_tenant_scoped_for_allowed (tr : Trace) (ev : Event)
    (hTrace : TraceSafe tr) (hIn : EventIn ev tr) (hallow : ev.decision = Decision.allow) :
    EventTenantScoped ev.principal.tenant ev :=
  traceSafe_allowed_event_tenant_scoped tr ev hTrace hIn hallow

end PFCore
