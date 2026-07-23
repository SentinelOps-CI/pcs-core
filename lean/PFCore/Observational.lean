import PFCore.Compositional
import PFCore.Handoff
import PFCore.NonInterference
import PFCore.ResourcePattern

/-!
# PF-Core observational equivalence (conservative tenant projection)

This module formalizes a **conservative observational vocabulary** for PF-Core traces.
It does **not** claim full global non-interference, absence of covert channels, or
indistinguishability under arbitrary adversaries. Projections retain only **allowed**
events whose principal tenant matches the observer tenant; denied and cross-tenant
events are classified as high-sensitivity and omitted from the low view.

**Naming:** The proved single-trace observational property is
`TenantProjectionIsolation`. Prefer that name in user-facing material. The Lean
abbreviation `NonInterference` is a **compatibility alias** only; paired-execution
`NonInterference` is reserved for a future schema/kernel version (see
`PairedExecution.lean`).
-/

namespace PFCore

/-- Low-sensitivity event for observer `tenant`: allowed and attributed to `tenant`. -/
def LowEvent (tenant : String) (ev : Event) : Prop :=
  ev.decision = Decision.allow ∧ ev.principal.tenant = tenant

/-- High-sensitivity event for observer `tenant`: not low-visible. -/
def HighEvent (tenant : String) (ev : Event) : Prop :=
  ¬ LowEvent tenant ev

def lowEventD (tenant : String) (ev : Event) : Bool :=
  match ev.decision with
  | Decision.deny => false
  | Decision.allow => decide (ev.principal.tenant = tenant)

/--
**Meaning:** Low-event decider matches allowed events whose principal tenant equals `tenant`.

**Trusted use:** Runtime projection alignment for tenant-scoped observational views.

**Does not imply:** Resource tenant alignment, covert-channel freedom, or full non-interference.
-/
theorem lowEventD_sound (tenant : String) (ev : Event) :
    lowEventD tenant ev = true ↔ LowEvent tenant ev := by
  cases ev with
  | mk _ p a d =>
    cases d <;> simp [lowEventD, LowEvent, decide_eq_true_iff]

/--
**Meaning:** Denied events never appear in a tenant's low projection (deny-side NI bound).

**Trusted use:** Scheduler-agnostic observational bound — deny decisions are high for all observers.

**Does not imply:** Deny paths are side-channel free or indistinguishable under timing.
-/
theorem deny_event_not_low (tenant : String) (ev : Event) (hdeny : ev.decision = Decision.deny) :
    ¬ LowEvent tenant ev := by
  intro hLow
  rcases hLow with ⟨hallow, _⟩
  rw [hdeny] at hallow
  cases hallow

/--
**Meaning:** Denied events are high-sensitivity for every observer tenant.

**Trusted use:** Deny-event observational classification aligned with runtime projection.

**Does not imply:** Full global non-interference or covert-channel freedom on deny paths.
-/
theorem deny_event_is_high (tenant : String) (ev : Event) (hdeny : ev.decision = Decision.deny) :
    HighEvent tenant ev :=
  fun hLow => absurd hLow (deny_event_not_low tenant ev hdeny)

/--
**Meaning:** Project trace to low-visible allowed events for `tenant` (oldest-first).

**Trusted use:** Conservative tenant observation function for equivalence claims.

**Does not imply:** Completeness of runtime logging or hash-chain integrity.
-/
def TraceProjection (tenant : String) : Trace → List Event
  | Trace.empty => []
  | Trace.cons tr ev =>
    if lowEventD tenant ev then
      TraceProjection tenant tr ++ [ev]
    else
      TraceProjection tenant tr

/--
**Meaning:** Membership in `TraceProjection tenant tr` iff the event occurs in `tr` and is low.

**Trusted use:** Relating projected lists to structural trace membership.

**Does not imply:** Semantic equality of events beyond structural `Event` identity.
-/
theorem traceProjection_mem (tenant : String) (tr : Trace) (ev : Event) :
    ev ∈ TraceProjection tenant tr ↔ EventIn ev tr ∧ LowEvent tenant ev := by
  induction tr with
  | empty =>
    simp [TraceProjection, EventIn, LowEvent]
  | cons tr' e ih =>
    by_cases hlow : lowEventD tenant e
    · simp [TraceProjection, hlow, lowEventD_sound]
      constructor
      · intro h
        simp [List.mem_append, List.mem_singleton] at h
        cases h with
        | inl htail =>
          rcases ih.mp htail with ⟨hIn, hLow⟩
          exact ⟨Or.inr hIn, hLow⟩
        | inr heq =>
          subst heq
          exact ⟨Or.inl rfl, (lowEventD_sound tenant ev).mp hlow⟩
      · intro ⟨hIn, hLow⟩
        cases hIn with
        | inl heq =>
          subst heq
          simp [(lowEventD_sound tenant ev).mpr hLow]
        | inr hIn' =>
          exact Or.inl (ih.mpr ⟨hIn', hLow⟩)
    · simp [TraceProjection, hlow, lowEventD_sound]
      constructor
      · intro h
        rcases ih.mp h with ⟨hIn, hLow⟩
        exact ⟨Or.inr hIn, hLow⟩
      · intro ⟨hIn, hLow⟩
        cases hIn with
        | inl heq =>
          subst heq
          have ht := (lowEventD_sound tenant ev).mpr hLow
          simp [ht] at hlow
        | inr hIn' =>
          exact ih.mpr ⟨hIn', hLow⟩

/--
**Meaning:** Denied events are omitted from every tenant low projection.

**Trusted use:** Trace-level deny-side projection bound (no timing or scheduler model).

**Does not imply:** Cross-trace indistinguishability or completeness of logged denies.
-/
theorem deny_event_not_in_trace_projection (tenant : String) (tr : Trace) (ev : Event)
    (hdeny : ev.decision = Decision.deny) (_hIn : EventIn ev tr) :
    ev ∉ TraceProjection tenant tr := by
  intro hMem
  exact deny_event_not_low tenant ev hdeny ((traceProjection_mem tenant tr ev).mp hMem).right

/--
**Meaning:** Two traces are observationally equivalent for `tenant` when low projections match.

**Trusted use:** Conservative observational equivalence (allowed same-tenant view only).

**Does not imply:** Full non-interference, indistinguishability under scheduling, or deny-side privacy.
-/
def ObservationallyEquivalentForTenant (tenant : String) (tr1 tr2 : Trace) : Prop :=
  TraceProjection tenant tr1 = TraceProjection tenant tr2

/--
**Meaning:** Safe traces place every low-projected event within tenant-scoped resources.

**Trusted use:** Primary link from `TraceSafe` to tenant-scoped low observations.

**Does not imply:** Full global non-interference, covert channels, or high-event isolation.
-/
theorem traceSafe_implies_low_events_tenant_scoped (tenant : String) (tr : Trace)
    (hTrace : TraceSafe tr) :
    ∀ ev, ev ∈ TraceProjection tenant tr → EventTenantScoped tenant ev := by
  intro ev hMem
  rcases (traceProjection_mem tenant tr ev).mp hMem with ⟨hIn, hLow⟩
  rcases hLow with ⟨hallow, htenant⟩
  subst htenant
  exact eventSafe_allow_implies_tenant_scoped ev
    (event_in_safe_trace_is_safe tr ev hTrace hIn) hallow

/-- Event attributed to `tenantHigh` (principal tenant equals `tenantHigh`). -/
def HighTenantEvent (tenantHigh : String) (ev : Event) : Prop :=
  ev.principal.tenant = tenantHigh

/--
**Meaning:** Conservative single-trace **tenant projection isolation** for distinct
tenants: the `TraceProjection tenantLow` view excludes every
`HighTenantEvent tenantHigh`, and every projected event is `LowEvent tenantLow`.
When `tenantLow = tenantHigh` the predicate is vacuously satisfied.

**Trusted use:** User-facing name for the proved observational bound (not paired-
execution non-interference).

**Does not imply:** Covert channels, timing leaks, deny-side information flow, handoff
across tenants, paired executions, or indistinguishability under schedulers not
recorded in PF-Core events.
-/
def TenantProjectionIsolation (tenantLow tenantHigh : String) (tr : Trace) : Prop :=
  tenantLow = tenantHigh ∨
    ((∀ ev, ev ∈ TraceProjection tenantLow tr → LowEvent tenantLow ev) ∧
      (∀ ev, EventIn ev tr → HighTenantEvent tenantHigh ev → HighEvent tenantLow ev))

/--
Compatibility alias for `TenantProjectionIsolation`. Prefer the latter name.
Reserved: a future paired-execution theorem family may reclaim `NonInterference`.
-/
abbrev NonInterference := TenantProjectionIsolation

def listAllLowEventD (tenantLow : String) : List Event → Bool
  | [] => true
  | ev :: rest => lowEventD tenantLow ev && listAllLowEventD tenantLow rest

def highTenantEventsHighForLowTraceD (tenantLow tenantHigh : String) (tr : Trace) : Bool :=
  match tr with
  | Trace.empty => true
  | Trace.cons tr' ev =>
    highTenantEventsHighForLowTraceD tenantLow tenantHigh tr' &&
      (if ev.principal.tenant == tenantHigh then ! lowEventD tenantLow ev else true)

def tenantProjectionIsolationD (tenantLow tenantHigh : String) (tr : Trace) : Bool :=
  if tenantLow == tenantHigh then
    true
  else
    listAllLowEventD tenantLow (TraceProjection tenantLow tr) &&
      highTenantEventsHighForLowTraceD tenantLow tenantHigh tr

/-- Compatibility alias for `tenantProjectionIsolationD`. -/
abbrev nonInterferenceD := tenantProjectionIsolationD

/--
**Meaning:** `listAllLowEventD` reflects universal low-event membership on a list.

**Trusted use:** Building block for `nonInterferenceD_sound`.

**Does not imply:** Events in the list occur in any particular trace order.
-/
theorem listAllLowEventD_sound (tenantLow : String) : ∀ (l : List Event),
    listAllLowEventD tenantLow l = true ↔ ∀ ev, ev ∈ l → LowEvent tenantLow ev
  | [] => by simp [listAllLowEventD, LowEvent]
  | ev :: rest => by
    have ih := listAllLowEventD_sound tenantLow rest
    rw [listAllLowEventD, Bool.and_eq_true, lowEventD_sound tenantLow ev, ih]
    constructor
    · intro ⟨hEv, hRest⟩ e hMem
      rcases List.mem_cons.mp hMem with (rfl | hmem)
      · exact hEv
      · exact hRest e hmem
    · intro h
      exact ⟨h ev (List.mem_cons_self _ _), fun e hmem => h e (List.mem_cons_of_mem _ hmem)⟩

/--
**Meaning:** `highTenantEventsHighForLowTraceD` reflects high-tenant events being high for `tenantLow`.

**Trusted use:** Building block for `nonInterferenceD_sound`.

**Does not imply:** Cross-tenant allows were denied or covert channels are absent.
-/
theorem highTenantEventsHighForLowTraceD_sound (tenantLow tenantHigh : String) (tr : Trace) :
    highTenantEventsHighForLowTraceD tenantLow tenantHigh tr = true ↔
      ∀ ev, EventIn ev tr → HighTenantEvent tenantHigh ev → HighEvent tenantLow ev := by
  induction tr with
  | empty =>
    simp [highTenantEventsHighForLowTraceD, EventIn, HighTenantEvent, HighEvent]
  | cons tr' ev ih =>
    simp only [highTenantEventsHighForLowTraceD, Bool.and_eq_true, EventIn]
    rw [ih]
    by_cases ht : ev.principal.tenant == tenantHigh
    · have htEq : ev.principal.tenant = tenantHigh := (beq_iff_eq).mp ht
      simp only [ht, if_true]
      constructor
      · intro ⟨hTail, hHead⟩ e hIn hHigh
        cases hIn with
        | inl heq =>
          subst heq
          intro hLow
          have hld : lowEventD tenantLow e = false := by
            revert hHead
            cases hb : lowEventD tenantLow e <;> simp [hb] at * <;> first | contradiction | rfl
          exact nomatch hld.symm.trans ((lowEventD_sound tenantLow e).mpr hLow)
        | inr hIn' =>
          exact hTail e hIn' hHigh
      · intro h
        refine ⟨fun e hIn hHigh => h e (Or.inr hIn) hHigh, ?_⟩
        by_cases hld : lowEventD tenantLow ev
        · exfalso
          exact (h ev (Or.inl rfl) htEq) ((lowEventD_sound tenantLow ev).mp hld)
        · simp [hld]
    · have hne : ev.principal.tenant ≠ tenantHigh := by
        intro heq
        have hb : (ev.principal.tenant == tenantHigh) = true := (beq_iff_eq).mpr heq
        rw [hb] at ht
        simp at ht
      simp only [ht]
      constructor
      · intro ⟨hTail, _⟩ e hIn hHigh
        cases hIn with
        | inl heq =>
          subst heq
          exact absurd hHigh hne
        | inr hIn' =>
          exact hTail e hIn' hHigh
      · intro h
        exact ⟨fun e hIn hHigh => h e (Or.inr hIn) hHigh, rfl⟩

/--
**Meaning:** Tenant-projection isolation decider matches `TenantProjectionIsolation`.

**Trusted use:** Runtime `--non-interference` / generated `concrete_non_interference_prop`
alignment (CLI flag name retained for compatibility).

**Does not imply:** Paired-execution non-interference, covert channels, or timing leaks.
-/
theorem tenantProjectionIsolationD_sound (tenantLow tenantHigh : String) (tr : Trace) :
    tenantProjectionIsolationD tenantLow tenantHigh tr = true ↔
      TenantProjectionIsolation tenantLow tenantHigh tr := by
  simp only [tenantProjectionIsolationD, TenantProjectionIsolation]
  by_cases hEq : tenantLow == tenantHigh
  · rw [if_pos hEq]
    have ht : tenantLow = tenantHigh := (beq_iff_eq).mp hEq
    constructor
    · intro _; exact Or.inl ht
    · intro h
      cases h with
      | inl _ => rfl
      | inr _ => rfl
  · rw [if_neg hEq]
    have hne : tenantLow ≠ tenantHigh := by
      intro heq
      have hb : (tenantLow == tenantHigh) = true := (beq_iff_eq).mpr heq
      rw [hb] at hEq
      simp at hEq
    rw [Bool.and_eq_true, listAllLowEventD_sound, highTenantEventsHighForLowTraceD_sound]
    constructor
    · intro ⟨hLow, hHigh⟩; exact Or.inr ⟨hLow, hHigh⟩
    · intro h
      cases h with
      | inl heq => exact absurd heq hne
      | inr hp => exact hp

/-- Compatibility alias for `tenantProjectionIsolationD_sound`. -/
theorem nonInterferenceD_sound (tenantLow tenantHigh : String) (tr : Trace) :
    nonInterferenceD tenantLow tenantHigh tr = true ↔ NonInterference tenantLow tenantHigh tr :=
  tenantProjectionIsolationD_sound tenantLow tenantHigh tr

theorem traceProjection_low_only (tenantLow : String) (tr : Trace) :
    (∀ ev, ev ∈ TraceProjection tenantLow tr → LowEvent tenantLow ev) := by
  intro ev hMem
  exact (traceProjection_mem tenantLow tr ev).mp hMem |>.right

theorem high_tenant_event_not_low_for_distinct_observer
    (tenantLow tenantHigh : String) (ev : Event)
    (hDiff : tenantLow ≠ tenantHigh) (hHigh : HighTenantEvent tenantHigh ev) :
    HighEvent tenantLow ev := by
  intro hLow
  rcases hLow with ⟨_, hTenantLow⟩
  rw [hHigh] at hTenantLow
  exact hDiff hTenantLow.symm

theorem high_tenant_events_high_for_low_observer
    (tenantLow tenantHigh : String) (tr : Trace) (hDiff : tenantLow ≠ tenantHigh) :
    ∀ ev, EventIn ev tr → HighTenantEvent tenantHigh ev → HighEvent tenantLow ev := by
  intro ev hIn hHigh
  exact high_tenant_event_not_low_for_distinct_observer tenantLow tenantHigh ev hDiff hHigh

/--
**Meaning:** Distinct-tenant projection isolation holds for every trace (definitional).

**Trusted use:** Base case for observational isolation; high-tenant events never enter
low projection.

**Does not imply:** Cross-trace indistinguishability or absence of covert channels.
-/
theorem tenant_projection_isolation_definitional (tenantLow tenantHigh : String) (tr : Trace)
    (hDiff : tenantLow ≠ tenantHigh) :
    TenantProjectionIsolation tenantLow tenantHigh tr := by
  right
  constructor
  · exact traceProjection_low_only tenantLow tr
  · intro ev hIn hHigh
    exact high_tenant_events_high_for_low_observer tenantLow tenantHigh tr hDiff ev hIn hHigh

/-- Compatibility alias. -/
theorem non_interference_definitional (tenantLow tenantHigh : String) (tr : Trace)
    (hDiff : tenantLow ≠ tenantHigh) :
    NonInterference tenantLow tenantHigh tr :=
  tenant_projection_isolation_definitional tenantLow tenantHigh tr hDiff

theorem tenant_projection_isolation_same_tenant (tenant : String) (tr : Trace) :
    TenantProjectionIsolation tenant tenant tr := by
  left; rfl

theorem non_interference_same_tenant (tenant : String) (tr : Trace) :
    NonInterference tenant tenant tr :=
  tenant_projection_isolation_same_tenant tenant tr

/--
**Meaning:** `TraceSafe` yields `TenantProjectionIsolation` for any tenant pair.

**Trusted use:** Primary observational isolation link from trace safety.

**Does not imply:** Paired-execution NI, timing, or handoff across tenants.
-/
theorem traceSafe_implies_tenant_projection_isolation
    (tenantLow tenantHigh : String) (tr : Trace) (_hTrace : TraceSafe tr) :
    TenantProjectionIsolation tenantLow tenantHigh tr := by
  by_cases hEq : tenantLow = tenantHigh
  · left; exact hEq
  · exact tenant_projection_isolation_definitional tenantLow tenantHigh tr hEq

/-- Compatibility alias for `traceSafe_implies_tenant_projection_isolation`. -/
theorem traceSafe_implies_non_interference (tenantLow tenantHigh : String) (tr : Trace)
    (hTrace : TraceSafe tr) :
    NonInterference tenantLow tenantHigh tr :=
  traceSafe_implies_tenant_projection_isolation tenantLow tenantHigh tr hTrace

/--
**Meaning:** `traceSafeD` implies the tenant-projection isolation decider.

**Trusted use:** Linking Lean kernel deciders to observational isolation certificates.

**Does not imply:** Paired-execution non-interference or covert-channel freedom.
-/
theorem traceSafeD_implies_tenantProjectionIsolationD
    (tenantLow tenantHigh : String) (tr : Trace) (h : traceSafeD tr = true) :
    tenantProjectionIsolationD tenantLow tenantHigh tr = true :=
  (tenantProjectionIsolationD_sound tenantLow tenantHigh tr).mpr
    (traceSafe_implies_tenant_projection_isolation tenantLow tenantHigh tr
      ((traceSafeD_sound tr).mp h))

theorem traceSafeD_implies_nonInterferenceD (tenantLow tenantHigh : String) (tr : Trace)
    (h : traceSafeD tr = true) :
    nonInterferenceD tenantLow tenantHigh tr = true :=
  traceSafeD_implies_tenantProjectionIsolationD tenantLow tenantHigh tr h

/--
**Meaning:** `TraceSafe` yields both `TenantIsolation` and `TenantProjectionIsolation`.

**Trusted use:** Single entry point linking trace safety and observational isolation.

**Does not imply:** Paired-execution non-interference or covert-channel freedom.
-/
theorem traceSafe_implies_tenant_isolation_and_projection_isolation
    (tenantLow tenantHigh : String) (tr : Trace) (hTrace : TraceSafe tr) :
    TenantIsolation tr ∧ TenantProjectionIsolation tenantLow tenantHigh tr :=
  ⟨traceSafe_implies_tenant_isolation tr hTrace,
    traceSafe_implies_tenant_projection_isolation tenantLow tenantHigh tr hTrace⟩

theorem traceSafe_implies_tenant_isolation_and_non_interference
    (tenantLow tenantHigh : String) (tr : Trace) (hTrace : TraceSafe tr) :
    TenantIsolation tr ∧ NonInterference tenantLow tenantHigh tr :=
  traceSafe_implies_tenant_isolation_and_projection_isolation tenantLow tenantHigh tr hTrace

/--
**Meaning:** `TenantIsolation` implies projection isolation for distinct tenants.

**Trusted use:** Link observational isolation to runtime `--tenant-isolation` alignment.

**Does not imply:** Denied cross-tenant events are side-channel free.
-/
theorem tenantIsolation_implies_tenant_projection_isolation
    (tenantLow tenantHigh : String) (tr : Trace)
    (hDiff : tenantLow ≠ tenantHigh) (_hTI : TenantIsolation tr) :
    TenantProjectionIsolation tenantLow tenantHigh tr :=
  tenant_projection_isolation_definitional tenantLow tenantHigh tr hDiff

theorem tenantIsolation_implies_non_interference (tenantLow tenantHigh : String) (tr : Trace)
    (hDiff : tenantLow ≠ tenantHigh) (hTI : TenantIsolation tr) :
    NonInterference tenantLow tenantHigh tr :=
  tenantIsolation_implies_tenant_projection_isolation tenantLow tenantHigh tr hDiff hTI

/--
**Meaning:** `TraceCrossTenantSafe` supports NI by ensuring cross-tenant allows are denied.

**Trusted use:** Connects cross-tenant safety to observational high/low classification.

**Does not imply:** Full global non-interference.
-/
theorem traceCrossTenantSafe_implies_high_tenant_not_low
    (tenantLow tenantHigh : String) (tr : Trace) (ev : Event)
    (hDiff : tenantLow ≠ tenantHigh) (_hCTS : TraceCrossTenantSafe tr)
    (_hIn : EventIn ev tr) (hHigh : HighTenantEvent tenantHigh ev) :
    HighEvent tenantLow ev :=
  high_tenant_event_not_low_for_distinct_observer tenantLow tenantHigh ev hDiff hHigh

/--
**Meaning:** Equal low projections imply observational equivalence (definitional).

**Trusted use:** Relating projection-based NI to `ObservationallyEquivalentForTenant`.

**Does not imply:** Traces with different high events but same projection exist or are safe.
-/
theorem low_projection_eq_observational (tenantLow : String) (tr1 tr2 : Trace)
    (h : TraceProjection tenantLow tr1 = TraceProjection tenantLow tr2) :
    ObservationallyEquivalentForTenant tenantLow tr1 tr2 :=
  h

/--
**Meaning:** Under `TenantProjectionIsolation`, matching low projections on distinct
traces yields observational equivalence for the low tenant.

**Trusted use:** Partial observational isolation: low view depends only on low-visible events.

**Does not imply:** Existence of alternative high traces or scheduler independence.
-/
theorem tenant_projection_isolation_observational_equivalence
    (tenantLow tenantHigh : String) (tr1 tr2 : Trace)
    (_hNI1 : TenantProjectionIsolation tenantLow tenantHigh tr1)
    (_hNI2 : TenantProjectionIsolation tenantLow tenantHigh tr2)
    (hProj : TraceProjection tenantLow tr1 = TraceProjection tenantLow tr2) :
    ObservationallyEquivalentForTenant tenantLow tr1 tr2 :=
  low_projection_eq_observational tenantLow tr1 tr2 hProj

theorem non_interference_observational_equivalence (tenantLow tenantHigh : String)
    (tr1 tr2 : Trace)
    (hNI1 : NonInterference tenantLow tenantHigh tr1)
    (hNI2 : NonInterference tenantLow tenantHigh tr2)
    (hProj : TraceProjection tenantLow tr1 = TraceProjection tenantLow tr2) :
    ObservationallyEquivalentForTenant tenantLow tr1 tr2 :=
  tenant_projection_isolation_observational_equivalence tenantLow tenantHigh tr1 tr2
    hNI1 hNI2 hProj

/--
**Meaning:** Low projection of an appended trace equals append of low projections.

**Trusted use:** Compositional observational NI under sequential trace composition.

**Does not imply:** Scheduler independence or covert-channel freedom.
-/
theorem traceProjection_append (tenant : String) (tr1 tr2 : Trace) :
    TraceProjection tenant (Trace.append tr1 tr2) =
      TraceProjection tenant tr1 ++ TraceProjection tenant tr2 := by
  induction tr2 with
  | empty =>
    simp [TraceProjection, Trace.append, Trace.ofEvents, Trace.events]
  | cons tr' ev ih =>
    rw [trace_append_cons]
    by_cases hlow : lowEventD tenant ev
    · simp [TraceProjection, hlow, lowEventD_sound, ih, List.append_assoc]
    · simp [TraceProjection, hlow, lowEventD_sound, ih]

/--
**Meaning:** Sequential composition preserves `TenantProjectionIsolation`.

**Trusted use:** Compositional observational isolation for distinct tenant pairs.

**Does not imply:** Paired-execution NI, timing leaks, or covert channels.
-/
theorem trace_append_preserves_tenant_projection_isolation
    (tenantLow tenantHigh : String) (tr1 tr2 : Trace)
    (_h1 : TenantProjectionIsolation tenantLow tenantHigh tr1)
    (_h2 : TenantProjectionIsolation tenantLow tenantHigh tr2) :
    TenantProjectionIsolation tenantLow tenantHigh (Trace.append tr1 tr2) := by
  by_cases hEq : tenantLow = tenantHigh
  · exact Or.inl hEq
  · have hDiff : tenantLow ≠ tenantHigh := by
      intro heq
      exact hEq heq
    exact tenant_projection_isolation_definitional tenantLow tenantHigh
      (Trace.append tr1 tr2) hDiff

theorem trace_append_preserves_non_interference (tenantLow tenantHigh : String) (tr1 tr2 : Trace)
    (h1 : NonInterference tenantLow tenantHigh tr1)
    (h2 : NonInterference tenantLow tenantHigh tr2) :
    NonInterference tenantLow tenantHigh (Trace.append tr1 tr2) :=
  trace_append_preserves_tenant_projection_isolation tenantLow tenantHigh tr1 tr2 h1 h2

/--
**Meaning:** `TraceSafe` on both components yields NI on their append (compositional link).

**Trusted use:** Multi-segment trace certificates with observational NI discharge.

**Does not imply:** Cross-trace indistinguishability under adversarial scheduling.
-/
theorem traceSafe_append_implies_non_interference (tenantLow tenantHigh : String) (tr1 tr2 : Trace)
    (h1 : TraceSafe tr1) (h2 : TraceSafe tr2) :
    NonInterference tenantLow tenantHigh (Trace.append tr1 tr2) :=
  trace_append_preserves_non_interference tenantLow tenantHigh tr1 tr2
    (traceSafe_implies_non_interference tenantLow tenantHigh tr1 h1)
    (traceSafe_implies_non_interference tenantLow tenantHigh tr2 h2)

/--
**Meaning:** `TraceSafeR` append implies base `TraceSafe` append and conservative NI.

**Trusted use:** Resource-pattern compositional chain with observational NI.

**Does not imply:** Kernel `TraceSafe` alone discharges resource patterns.
-/
theorem traceSafeR_append_implies_non_interference (tenantLow tenantHigh : String) (tr1 tr2 : Trace)
    (h1 : TraceSafeR tr1) (h2 : TraceSafeR tr2) :
    NonInterference tenantLow tenantHigh (Trace.append tr1 tr2) :=
  traceSafe_append_implies_non_interference tenantLow tenantHigh tr1 tr2
    (traceSafeR_implies_traceSafe tr1 h1) (traceSafeR_implies_traceSafe tr2 h2)

/--
**Meaning:** Under `HandoffSafe` and `TraceSafe`, conservative NI holds with same-tenant handoff.

**Trusted use:** Handoff-side tenant NI bound (cross-tenant handoff excluded by `HandoffSafe`).

**Does not imply:** Post-handoff event isolation without trace safety or explicit downgrade policy.
-/
theorem handoffSafe_traceSafe_non_interference (h : Handoff) (hSafe : HandoffSafe h)
    (tenantLow tenantHigh : String) (tr : Trace) (hTrace : TraceSafe tr) :
    NonInterference tenantLow tenantHigh tr ∧ h.fromPrincipal.tenant = h.toPrincipal.tenant := by
  exact ⟨traceSafe_implies_non_interference tenantLow tenantHigh tr hTrace, hSafe.right⟩

/--
**Meaning:** Cross-tenant handoff cannot be `HandoffSafe`; NI across tenants via handoff remains open.

**Trusted use:** Documents downgrade/cross-tenant handoff as out-of-scope for conservative NI.

**Does not imply:** Runtime rejects invalid handoffs or post-handoff isolation.
-/
theorem handoffSafe_excludes_cross_tenant_handoff (h : Handoff) (tFrom tTo : String)
    (hFrom : h.fromPrincipal.tenant = tFrom) (hTo : h.toPrincipal.tenant = tTo)
    (hDiff : tFrom ≠ tTo) : ¬ HandoffSafe h :=
  handoffSafe_forbids_distinct_tenant h tFrom tTo hFrom hTo hDiff

end PFCore

