import PFCore.Event

/-!
# PF-Core traces and trace-level safety
-/

namespace PFCore

/-- Ordered action trace (oldest event nearest `empty`). -/
inductive Trace where
  | empty
  | cons : Trace → Event → Trace
deriving Repr

def TraceSafe : Trace → Prop
  | Trace.empty => True
  | Trace.cons tr ev => TraceSafe tr ∧ EventSafe ev

def traceSafeD : Trace → Bool
  | Trace.empty => true
  | Trace.cons tr ev => traceSafeD tr && eventSafeD ev

/-- Event membership in a trace (structural equality on `Event`). -/
def EventIn (ev : Event) : Trace → Prop
  | Trace.empty => False
  | Trace.cons tr e => ev = e ∨ EventIn ev tr

def eventInD (ev : Event) (tr : Trace) : Bool :=
  match tr with
  | Trace.empty => false
  | Trace.cons tr' e => decide (ev == e) || eventInD ev tr'

theorem traceSafe_empty : TraceSafe Trace.empty := trivial

theorem traceSafe_cons (tr : Trace) (ev : Event) :
    TraceSafe (Trace.cons tr ev) ↔ TraceSafe tr ∧ EventSafe ev := by
  rfl

theorem traceSafeD_sound (tr : Trace) :
    traceSafeD tr = true ↔ TraceSafe tr := by
  induction tr with
  | empty => simp [traceSafeD, TraceSafe]
  | cons tr ev ih =>
    simp [traceSafeD, TraceSafe, eventSafeD_sound, ih, and_left_comm]

theorem eventInD_sound (ev : Event) (tr : Trace) :
    eventInD ev tr = true ↔ EventIn ev tr := by
  induction tr with
  | empty => simp [eventInD, EventIn]
  | cons tr' e ih =>
    simp [eventInD, EventIn, ih, beq_iff_eq, decide_eq_true_iff]

end PFCore
