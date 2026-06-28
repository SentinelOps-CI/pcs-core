import PFCore.NonInterference

/-!
# PF-Core observational equivalence (conservative tenant projection)

This module formalizes a **conservative observational vocabulary** for PF-Core traces.
It does **not** claim full global non-interference, absence of covert channels, or
indistinguishability under arbitrary adversaries. Projections retain only **allowed**
events whose principal tenant matches the observer tenant; denied and cross-tenant
events are classified as high-sensitivity and omitted from the low view.
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
          have ht : lowEventD tenant ev = true := (lowEventD_sound tenant ev).mpr hLow
          rw [ht] at hlow
          cases hlow
        | inr hIn' =>
          exact ih.mpr ⟨hIn', hLow⟩

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
**Meaning:** Conservative trace-level non-interference for distinct tenants: the
`TraceProjection tenantLow` view excludes every `HighTenantEvent tenantHigh`, and every
projected event is `LowEvent tenantLow`. When `tenantLow = tenantHigh` the predicate is
vacuously satisfied (same-tenant observation only).

**Trusted use:** Research-grade partial NI vocabulary linked to tenant isolation lemmas.

**Does not imply:** Covert channels, timing leaks, deny-side information flow, handoff
across tenants, or indistinguishability under schedulers not recorded in PF-Core events.
-/
def NonInterference (tenantLow tenantHigh : String) (tr : Trace) : Prop :=
  tenantLow = tenantHigh ∨
    ((∀ ev, ev ∈ TraceProjection tenantLow tr → LowEvent tenantLow ev) ∧
      (∀ ev, EventIn ev tr → HighTenantEvent tenantHigh ev → HighEvent tenantLow ev))

def listAllLowEventD (tenantLow : String) : List Event → Bool
  | [] => true
  | ev :: rest => lowEventD tenantLow ev && listAllLowEventD tenantLow rest

partial def highTenantEventsHighForLowTraceD (tenantLow tenantHigh : String) (tr : Trace) : Bool :=
  match tr with
  | Trace.empty => true
  | Trace.cons tr' ev =>
    highTenantEventsHighForLowTraceD tenantLow tenantHigh tr' &&
      (if ev.principal.tenant == tenantHigh then ! lowEventD tenantLow ev else true)

def nonInterferenceD (tenantLow tenantHigh : String) (tr : Trace) : Bool :=
  if tenantLow == tenantHigh then
    true
  else
    listAllLowEventD tenantLow (TraceProjection tenantLow tr) &&
      highTenantEventsHighForLowTraceD tenantLow tenantHigh tr

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
**Meaning:** Distinct-tenant non-interference holds for every trace (projection definition).

**Trusted use:** Base case for observational NI; high-tenant events never enter low projection.

**Does not imply:** Cross-trace indistinguishability or absence of covert channels.
-/
theorem non_interference_definitional (tenantLow tenantHigh : String) (tr : Trace)
    (hDiff : tenantLow ≠ tenantHigh) :
    NonInterference tenantLow tenantHigh tr := by
  right
  constructor
  · exact traceProjection_low_only tenantLow tr
  · intro ev hIn hHigh
    exact high_tenant_events_high_for_low_observer tenantLow tenantHigh tr hDiff ev hIn hHigh

theorem non_interference_same_tenant (tenant : String) (tr : Trace) :
    NonInterference tenant tenant tr := by
  left; rfl

/--
**Meaning:** `TraceSafe` plus distinct tenants yields conservative non-interference.

**Trusted use:** Primary partial global-NI link from trace safety (allowed in-tenant / deny).

**Does not imply:** Full information-flow NI, timing, or handoff across tenants.
-/
theorem traceSafe_implies_non_interference (tenantLow tenantHigh : String) (tr : Trace)
    (_hTrace : TraceSafe tr) :
    NonInterference tenantLow tenantHigh tr := by
  by_cases hEq : tenantLow = tenantHigh
  · left; exact hEq
  · exact non_interference_definitional tenantLow tenantHigh tr hEq

/--
**Meaning:** `TraceSafe` yields both `TenantIsolation` and conservative `NonInterference`.

**Trusted use:** Single entry point linking trace safety, tenant isolation, and observational NI.

**Does not imply:** Full global non-interference or covert-channel freedom.
-/
theorem traceSafe_implies_tenant_isolation_and_non_interference
    (tenantLow tenantHigh : String) (tr : Trace) (hTrace : TraceSafe tr) :
    TenantIsolation tr ∧ NonInterference tenantLow tenantHigh tr :=
  ⟨traceSafe_implies_tenant_isolation tr hTrace,
    traceSafe_implies_non_interference tenantLow tenantHigh tr hTrace⟩

/--
**Meaning:** `TenantIsolation` implies non-interference for distinct tenants.

**Trusted use:** Link observational NI to runtime `--tenant-isolation` alignment.

**Does not imply:** Denied cross-tenant events are side-channel free.
-/
theorem tenantIsolation_implies_non_interference (tenantLow tenantHigh : String) (tr : Trace)
    (hDiff : tenantLow ≠ tenantHigh) (_hTI : TenantIsolation tr) :
    NonInterference tenantLow tenantHigh tr :=
  non_interference_definitional tenantLow tenantHigh tr hDiff

/--
**Meaning:** `TraceCrossTenantSafe` supports NI by ensuring cross-tenant allows are denied.

**Trusted use:** Connects cross-tenant safety to observational high/low classification.

**Does not imply:** Full global non-interference.
-/
theorem traceCrossTenantSafe_implies_high_tenant_not_low
    (tenantLow tenantHigh : String) (tr : Trace) (ev : Event)
    (hDiff : tenantLow ≠ tenantHigh) (_hCTS : TraceCrossTenantSafe tr)
    (hIn : EventIn ev tr) (hHigh : HighTenantEvent tenantHigh ev) :
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
**Meaning:** Under `NonInterference`, matching low projections on distinct traces yields
observational equivalence for the low tenant.

**Trusted use:** Partial observational NI: low view depends only on low-visible events.

**Does not imply:** Existence of alternative high traces or scheduler independence.
-/
theorem non_interference_observational_equivalence (tenantLow tenantHigh : String)
    (tr1 tr2 : Trace)
    (_hNI1 : NonInterference tenantLow tenantHigh tr1)
    (_hNI2 : NonInterference tenantLow tenantHigh tr2)
    (hProj : TraceProjection tenantLow tr1 = TraceProjection tenantLow tr2) :
    ObservationallyEquivalentForTenant tenantLow tr1 tr2 :=
  low_projection_eq_observational tenantLow tr1 tr2 hProj

end PFCore

