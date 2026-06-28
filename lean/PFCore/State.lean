import PFCore.Transition

import PFCore.Compositional



/-!

# PF-Core operational state and handoff application



Handoff application on the rich `State` model from `Transition.lean`. State tracks

active principal, resource frame, and capability frame alongside trace safety

composition theorems.

-/



namespace PFCore



/-- Derive initial state from a principal (empty resource frame). -/

def initialState (p : Principal) : State :=

  { tenant := p.tenant

    activePrincipal := p

    resourceFrame := []

    capabilityFrame := p.capabilities }



/--

**Meaning:** Apply an event via operational `stepState`, falling back to unchanged state on deny.



**Trusted use:** Conservative event application before handoff modeling.



**Does not imply:** Denied events mutate state at runtime or replay validates ordering.

-/

def applyEvent (s : State) (ev : Event) : State :=

  match stepState s ev with

  | some s' => s'

  | none => s



/--

**Meaning:** Apply handoff: switch active principal and merge delegated capabilities.



**Trusted use:** Modeling capability transfer after `HandoffSafe` delegation.



**Does not imply:** Runtime principal mutation, temporal policy, or multi-principal registry.

-/

def HandoffApplies (h : Handoff) (s : State) : State :=
  let mergedCaps :=
    h.delegatedCapabilities ++
      h.toPrincipal.capabilities.filter (fun cap => cap ∉ h.delegatedCapabilities)
  { tenant := s.tenant
    activePrincipal := { h.toPrincipal with tenant := s.tenant, capabilities := mergedCaps }
    resourceFrame := s.resourceFrame
    capabilityFrame := mergedCaps }

private theorem applyEvent_preserves_frame_valid (s : State) (ev : Event) (hValid : FrameValid s) :
    FrameValid (applyEvent s ev) := by
  unfold applyEvent
  cases hstep : stepState s ev with
  | none =>
    simp [hstep]
    exact hValid
  | some s' =>
    simp [hstep]
    exact stepState_frame_preserved s s' ev (by unfold Applies; exact hstep) hValid

private theorem handoff_frame_valid (h : Handoff) (s : State) (_hSafe : HandoffSafe h) (hValid : FrameValid s) :
    FrameValid (HandoffApplies h s) := by
  rcases hValid with ⟨htenant, hframe, _⟩
  constructor
  · unfold HandoffApplies
    rfl
  · intro r hr
    exact hframe r hr
  · unfold HandoffApplies capabilityFrameSubset CapabilitySubset
    intro cap hmem
    exact hmem



/--

**Meaning:** Capabilities in post-handoff state came from the source delegation envelope

or were already held by the target principal.



**Trusted use:** State-level authority non-expansion after `HandoffApplies`.



**Does not imply:** Target may exercise capabilities without separate action safety checks.

-/

theorem handoff_applies_does_not_expand_authority (h : Handoff) (s : State) (cap : String) :

    HandoffSafe h → cap ∈ (HandoffApplies h s).capabilityFrame →

    HasCapability h.fromPrincipal cap ∨ HasCapability h.toPrincipal cap := by

  intro hsafe hmem

  unfold HandoffApplies at hmem

  simp only at hmem

  rcases List.mem_append.mp hmem with hdel | htarget

  · left

    exact handoff_does_not_expand_authority h cap hsafe hdel

  · right

    exact (List.mem_filter.mp htarget).1



/--

**Meaning:** Under `TraceSafe`, `HandoffSafe`, and `EventSafe`, extending the trace

with the handoff-related event preserves `TraceSafe`; delegated capabilities remain

bounded by the source principal; post-handoff state does not introduce authority

beyond source/target principals.



**Trusted use:** Compositional handoff + trace-safety certificates with operational state.



**Does not imply:** Full operational semantics, automatic `EventSafe` for handoff events,

or that intermediate principals may act without explicit capability checks.

-/

theorem handoff_preserves_trace_safe (tr : Trace) (s : State) (h : Handoff) (ev : Event) :

    TraceSafe tr → HandoffSafe h → EventSafe ev →

    TraceSafe (Trace.cons tr ev) ∧

    (∀ cap ∈ h.delegatedCapabilities, HasCapability h.fromPrincipal cap) ∧

    (∀ cap ∈ (HandoffApplies h (applyEvent s ev)).capabilityFrame,

      HasCapability h.fromPrincipal cap ∨ HasCapability h.toPrincipal cap) := by

  intro hTrace hHandoff hEvSafe

  refine ⟨safe_extension_preserves_trace_safe tr ev hTrace hEvSafe, ?_, ?_⟩

  · intro cap hmem

    exact handoff_does_not_expand_authority h cap hHandoff hmem

  · intro cap hmem

    exact handoff_applies_does_not_expand_authority h s cap hHandoff hmem



/--

**Meaning:** Strong handoff step: safe extension, frame validity preserved, bounded authority.



**Trusted use:** Research-grade handoff certificates combining state frames and trace safety.



**Does not imply:** Multi-hop handoff chains without separate composition lemmas.

-/

theorem handoff_preserves_trace_safe_strong (tr : Trace) (s : State) (h : Handoff) (ev : Event) :

    TraceSafe tr → HandoffSafe h → EventSafe ev → FrameValid s →

    TraceExtendsSafely tr ev →

    TraceSafe (Trace.cons tr ev) ∧ FrameValid (HandoffApplies h (applyEvent s ev)) ∧

    (∀ cap ∈ (HandoffApplies h (applyEvent s ev)).capabilityFrame,

      HasCapability h.fromPrincipal cap ∨ HasCapability h.toPrincipal cap) := by

  intro hTrace hHandoff hEvSafe hFrame hExt

  rcases handoff_preserves_trace_safe tr s h ev hTrace hHandoff hEvSafe with ⟨hTrSafe, _, hAuth⟩

  have hPostValid : FrameValid (applyEvent s ev) :=
    applyEvent_preserves_frame_valid s ev hFrame
  refine ⟨hTrSafe, handoff_frame_valid h (applyEvent s ev) hHandoff hPostValid, hAuth⟩



end PFCore

