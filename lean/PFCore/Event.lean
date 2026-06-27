import PFCore.Action

/-!
# PF-Core events and event-level safety
-/

namespace PFCore

/-- Authorization outcome recorded on an event. -/
inductive Decision where
  | allow
  | deny
deriving Repr, DecidableEq

/-- One principal action with an explicit authorization decision. -/
structure Event where
  id : String
  principal : Principal
  action : Action
  decision : Decision
deriving Repr, DecidableEq

/-- Allowed events must correspond to allowed actions under PF-Core rules. -/
def EventSafe (ev : Event) : Prop :=
  ev.decision = Decision.allow → ActionAllowed ev.principal ev.action

def eventSafeD (ev : Event) : Bool :=
  match ev.decision with
  | Decision.deny => true
  | Decision.allow => actionAllowedD ev.principal ev.action

/--
**Meaning:** The boolean `eventSafeD` decider reflects the `EventSafe` predicate.

**Trusted use:** Soundness link between per-event deciders and Prop-level event safety.

**Does not imply:** Denied events were safe to deny, or external policy correctness.
-/
theorem eventSafeD_sound (ev : Event) :
    eventSafeD ev = true ↔ EventSafe ev := by
  cases ev with
  | mk _ p a d =>
    cases d <;> simp [EventSafe, eventSafeD, actionAllowedD_sound]

end PFCore
