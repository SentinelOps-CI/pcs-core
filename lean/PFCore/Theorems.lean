import PFCore.Soundness

/-!
# PF-Core trace safety theorems (trusted catalog)
-/

namespace PFCore

/--
**Meaning:** If an event is safe and its decision is `allow`, the principal's action
was allowed under PF-Core capability and tenant rules.

**Trusted use:** Linking decider-checked event safety to action allowance on allowed
events in certificates and generated concrete proofs.

**Does not imply:** Denied events were correct, runtime enforcement, or domain-specific
policy satisfaction beyond PF-Core structural rules.
-/
theorem allowed_event_has_allowed_action (ev : Event) (h : EventSafe ev) (hallow : ev.decision = Decision.allow) :
    ActionAllowed ev.principal ev.action := by
  exact h hallow

/--
**Meaning:** Every event structurally present in a safe trace is itself safe.

**Trusted use:** Inductive reasoning over trace membership when `TraceSafe` is already established.

**Does not imply:** The trace is complete, replay-valid, or hash-chain consistent with runtime.
-/
theorem event_in_safe_trace_is_safe (tr : Trace) (ev : Event)
    (hTrace : TraceSafe tr) (hIn : EventIn ev tr) : EventSafe ev := by
  induction tr with
  | empty => simp [EventIn] at hIn
  | cons tr' head ih =>
    rcases hTrace with ⟨hTrSafe, hHeadSafe⟩
    simp [EventIn] at hIn
    cases hIn with
    | inl heq =>
      subst heq
      exact hHeadSafe
    | inr hIn' =>
      exact ih hTrSafe hIn'

/--
**Meaning:** Any allowed event inside a safe trace corresponds to an allowed action.

**Trusted use:** Prop-level discharge for generated `concrete_allowed_events_allowed` proofs.

**Does not imply:** All events in the trace were allowed, or that external contracts hold.
-/
theorem every_allowed_event_in_safe_trace_is_allowed (tr : Trace) (ev : Event)
    (hTrace : TraceSafe tr) (hIn : EventIn ev tr) (hallow : ev.decision = Decision.allow) :
    ActionAllowed ev.principal ev.action := by
  have hEv := event_in_safe_trace_is_safe tr ev hTrace hIn
  exact allowed_event_has_allowed_action ev hEv hallow

end PFCore
