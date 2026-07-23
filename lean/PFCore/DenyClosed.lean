import PFCore.Event
import PFCore.Handoff
import PFCore.ObservedEffect
import PFCore.Trace

/-!
# PF-Core deny-path closedness (optional EventSafe refinement)

Base `EventSafe` treats deny decisions as vacuously safe. This module adds an
optional refinement `EventSafeDenyClosed` that constrains the **declared** deny
record: no resource mutation, no side-effecting effect kinds, no tool invocation
observations, no delegated authority, and optional deny-reason consistency.

Base `EventSafe` / `TraceSafe` remain unchanged and compatible.
-/

namespace PFCore

/-- Effect kinds forbidden on a closed deny path (mutating / external). -/
def Effect.IsDenyPathForbidden : Effect → Prop
  | Effect.write | Effect.network | Effect.externalMessage
  | Effect.codeExecution | Effect.stateChange => True
  | Effect.read | Effect.custom _ => False

def effectIsDenyPathForbiddenD : Effect → Bool
  | Effect.write | Effect.network | Effect.externalMessage
  | Effect.codeExecution | Effect.stateChange => true
  | Effect.read | Effect.custom _ => false

theorem effectIsDenyPathForbiddenD_sound (e : Effect) :
    effectIsDenyPathForbiddenD e = true ↔ Effect.IsDenyPathForbidden e := by
  cases e <;> simp [effectIsDenyPathForbiddenD, Effect.IsDenyPathForbidden]

/-- No declared write footprint. -/
def NoResourceMutation (a : Action) : Prop :=
  a.writes = []

def noResourceMutationD (a : Action) : Bool :=
  decide (a.writes = [])

theorem noResourceMutationD_sound (a : Action) :
    noResourceMutationD a = true ↔ NoResourceMutation a := by
  simp [noResourceMutationD, NoResourceMutation, decide_eq_true_iff]

/-- No external-message effect declared. -/
def NoExternalMessage (a : Action) : Prop :=
  Effect.externalMessage ∉ a.effects

/-- No code-execution effect declared. -/
def NoCodeExecution (a : Action) : Prop :=
  Effect.codeExecution ∉ a.effects

/-- No deny-path-forbidden effects declared on the action. -/
def NoSideEffectingEffects (a : Action) : Prop :=
  ∀ e ∈ a.effects, ¬ Effect.IsDenyPathForbidden e

def noSideEffectingEffectsD (a : Action) : Bool :=
  a.effects.all (fun e => ! effectIsDenyPathForbiddenD e)

theorem noSideEffectingEffectsD_sound (a : Action) :
    noSideEffectingEffectsD a = true ↔ NoSideEffectingEffects a := by
  unfold noSideEffectingEffectsD NoSideEffectingEffects
  simp only [List.all_eq_true]
  constructor
  · intro h e he hSens
    have hb := h e he
    rw [(effectIsDenyPathForbiddenD_sound e).mpr hSens] at hb
    cases hb
  · intro h e he
    cases hb : effectIsDenyPathForbiddenD e
    · rfl
    · exact absurd ((effectIsDenyPathForbiddenD_sound e).mp hb) (h e he)

/-- Closed deny-path constraints on the event's declared action footprint. -/
def DenyPathClosed (ev : Event) : Prop :=
  ev.decision = Decision.deny →
    NoResourceMutation ev.action ∧ NoSideEffectingEffects ev.action

def denyPathClosedD (ev : Event) : Bool :=
  match ev.decision with
  | Decision.allow => true
  | Decision.deny => noResourceMutationD ev.action && noSideEffectingEffectsD ev.action

theorem denyPathClosedD_sound (ev : Event) :
    denyPathClosedD ev = true ↔ DenyPathClosed ev := by
  cases ev with
  | mk _ p a d =>
    cases d <;> simp [denyPathClosedD, DenyPathClosed, noResourceMutationD_sound,
      noSideEffectingEffectsD_sound, Bool.and_eq_true]

/-- Optional deny-reason vocabulary for policy consistency checks. -/
inductive DenyReason where
  | capabilityMissing
  | tenantMismatch
  | resourceScope
  | policyViolation
  | other : String → DenyReason
deriving Repr, DecidableEq

/--
Deny reasons may appear only on deny decisions. Allow events must not carry a
reason. Absence of a reason on deny is permitted (reason is optional metadata).
-/
def DenyReasonConsistent (ev : Event) (reason : Option DenyReason) : Prop :=
  match ev.decision, reason with
  | Decision.allow, none => True
  | Decision.allow, some _ => False
  | Decision.deny, _ => True

def denyReasonConsistentD (ev : Event) (reason : Option DenyReason) : Bool :=
  match ev.decision, reason with
  | Decision.allow, none => true
  | Decision.allow, some _ => false
  | Decision.deny, _ => true

theorem denyReasonConsistentD_sound (ev : Event) (reason : Option DenyReason) :
    denyReasonConsistentD ev reason = true ↔ DenyReasonConsistent ev reason := by
  cases ev with
  | mk _ _ _ d =>
    cases d <;> cases reason <;>
      simp [denyReasonConsistentD, DenyReasonConsistent]

/--
No tool invocation after denial: under instrumentation, a deny event must carry
an empty observation list (the tool was not executed).
-/
def NoToolInvocationAfterDenial (ev : Event) (obs : List ObservedEffect) : Prop :=
  ev.decision = Decision.deny → obs = []

def noToolInvocationAfterDenialD (ev : Event) (obs : List ObservedEffect) : Bool :=
  match ev.decision with
  | Decision.allow => true
  | Decision.deny => decide (obs = [])

theorem noToolInvocationAfterDenialD_sound (ev : Event) (obs : List ObservedEffect) :
    noToolInvocationAfterDenialD ev obs = true ↔ NoToolInvocationAfterDenial ev obs := by
  cases ev with
  | mk _ _ _ d =>
    cases d <;> simp [noToolInvocationAfterDenialD, NoToolInvocationAfterDenial,
      decide_eq_true_iff]

/-- No delegated authority on deny: accompanying handoff record must be absent. -/
def NoDelegatedAuthorityOnDeny (ev : Event) (h : Option Handoff) : Prop :=
  ev.decision = Decision.deny → h = none

def noDelegatedAuthorityOnDenyD (ev : Event) (h : Option Handoff) : Bool :=
  match ev.decision with
  | Decision.allow => true
  | Decision.deny =>
    match h with
    | none => true
    | some _ => false

theorem noDelegatedAuthorityOnDenyD_sound (ev : Event) (h : Option Handoff) :
    noDelegatedAuthorityOnDenyD ev h = true ↔ NoDelegatedAuthorityOnDeny ev h := by
  cases ev with
  | mk _ _ _ d =>
    cases d <;> cases h <;>
      simp [noDelegatedAuthorityOnDenyD, NoDelegatedAuthorityOnDeny]

/--
**Meaning:** Stronger event safety: base `EventSafe` plus closed deny-path
constraints on the declared action footprint.

**Trusted use:** Optional deny-closed certificates; does not alter base `EventSafe`.

**Does not imply:** Runtime suppressed the tool without instrumentation evidence,
or deny-reason policy correctness beyond `DenyReasonConsistent`.
-/
def EventSafeDenyClosed (ev : Event) : Prop :=
  EventSafe ev ∧ DenyPathClosed ev

def eventSafeDenyClosedD (ev : Event) : Bool :=
  eventSafeD ev && denyPathClosedD ev

theorem eventSafeDenyClosedD_sound (ev : Event) :
    eventSafeDenyClosedD ev = true ↔ EventSafeDenyClosed ev := by
  simp [eventSafeDenyClosedD, EventSafeDenyClosed, eventSafeD_sound, denyPathClosedD_sound,
    Bool.and_eq_true]

/--
**Meaning:** Deny-closed event safety refines base `EventSafe`.

**Trusted use:** Migration path; existing `EventSafe` proofs remain valid.

**Does not imply:** Deny-closed constraints without the refinement hypothesis.
-/
theorem eventSafeDenyClosed_implies_eventSafe (ev : Event)
    (h : EventSafeDenyClosed ev) : EventSafe ev :=
  h.left

/-- Allow events that are `EventSafe` are deny-closed (deny branch vacuous). -/
theorem eventSafe_allow_implies_eventSafeDenyClosed (ev : Event)
    (h : EventSafe ev) (hallow : ev.decision = Decision.allow) :
    EventSafeDenyClosed ev := by
  refine ⟨h, ?_⟩
  intro hdeny
  rw [hallow] at hdeny
  cases hdeny

/-- Denied deny-closed events have empty write footprint. -/
theorem eventSafeDenyClosed_deny_no_writes (ev : Event)
    (h : EventSafeDenyClosed ev) (hdeny : ev.decision = Decision.deny) :
    NoResourceMutation ev.action :=
  (h.right hdeny).left

/-- Denied deny-closed events declare no side-effecting effects. -/
theorem eventSafeDenyClosed_deny_no_side_effects (ev : Event)
    (h : EventSafeDenyClosed ev) (hdeny : ev.decision = Decision.deny) :
    NoSideEffectingEffects ev.action :=
  (h.right hdeny).right

/-- Trace-level deny-closed refinement. -/
def TraceSafeDenyClosed : Trace → Prop
  | Trace.empty => True
  | Trace.cons tr ev => TraceSafeDenyClosed tr ∧ EventSafeDenyClosed ev

def traceSafeDenyClosedD (tr : Trace) : Bool :=
  match tr with
  | Trace.empty => true
  | Trace.cons tr' ev => traceSafeDenyClosedD tr' && eventSafeDenyClosedD ev

theorem traceSafeDenyClosedD_sound (tr : Trace) :
    traceSafeDenyClosedD tr = true ↔ TraceSafeDenyClosed tr := by
  induction tr with
  | empty => simp [traceSafeDenyClosedD, TraceSafeDenyClosed]
  | cons tr' ev ih =>
    simp [traceSafeDenyClosedD, TraceSafeDenyClosed, eventSafeDenyClosedD_sound, ih,
      and_left_comm]

/--
**Meaning:** Deny-closed traces refine base `TraceSafe`.

**Trusted use:** Optional stronger certificates without breaking base proofs.

**Does not imply:** Base `TraceSafe` alone yields deny-closed constraints.
-/
theorem traceSafeDenyClosed_implies_traceSafe (tr : Trace) :
    TraceSafeDenyClosed tr → TraceSafe tr := by
  induction tr with
  | empty => intro _; trivial
  | cons tr' ev ih =>
    intro h
    rcases h with ⟨hTr, hEv⟩
    exact ⟨ih hTr, eventSafeDenyClosed_implies_eventSafe ev hEv⟩

/-- Package optional deny-path properties used by runtime mirrors. -/
structure DenyClosedBundle where
  event : Event
  observations : List ObservedEffect
  handoff : Option Handoff
  denyReason : Option DenyReason

def DenyClosedBundle.Holds (b : DenyClosedBundle) : Prop :=
  EventSafeDenyClosed b.event ∧
  NoToolInvocationAfterDenial b.event b.observations ∧
  NoDelegatedAuthorityOnDeny b.event b.handoff ∧
  DenyReasonConsistent b.event b.denyReason

def denyClosedBundleD (b : DenyClosedBundle) : Bool :=
  eventSafeDenyClosedD b.event &&
    noToolInvocationAfterDenialD b.event b.observations &&
    noDelegatedAuthorityOnDenyD b.event b.handoff &&
    denyReasonConsistentD b.event b.denyReason

theorem denyClosedBundleD_sound (b : DenyClosedBundle) :
    denyClosedBundleD b = true ↔ DenyClosedBundle.Holds b := by
  simp only [denyClosedBundleD, DenyClosedBundle.Holds, eventSafeDenyClosedD_sound,
    noToolInvocationAfterDenialD_sound, noDelegatedAuthorityOnDenyD_sound,
    denyReasonConsistentD_sound, Bool.and_eq_true]
  constructor
  · intro ⟨⟨⟨h1, h2⟩, h3⟩, h4⟩
    exact ⟨h1, h2, h3, h4⟩
  · intro ⟨h1, h2, h3, h4⟩
    exact ⟨⟨⟨h1, h2⟩, h3⟩, h4⟩

end PFCore
