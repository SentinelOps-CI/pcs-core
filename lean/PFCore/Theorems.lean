import PFCore.Soundness

/-!
# PF-Core trace safety theorems (trusted catalog)
-/

namespace PFCore

/-- From event safety, an allowed decision implies the action was allowed. -/
theorem allowed_event_has_allowed_action (ev : Event) (h : EventSafe ev) (hallow : ev.decision = Decision.allow) :
    ActionAllowed ev.principal ev.action := by
  exact h hallow

/-- Every event in a safe trace is itself safe. -/
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

/-- Any allowed event inside a safe trace corresponds to an allowed action. -/
theorem every_allowed_event_in_safe_trace_is_allowed (tr : Trace) (ev : Event)
    (hTrace : TraceSafe tr) (hIn : EventIn ev tr) (hallow : ev.decision = Decision.allow) :
    ActionAllowed ev.principal ev.action := by
  have hEv := event_in_safe_trace_is_safe tr ev hTrace hIn
  exact allowed_event_has_allowed_action ev hEv hallow

end PFCore
