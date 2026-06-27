import PFCore.ContractDecide
import PFCore.Handoff
import PFCore.Trace

/-!
# PF-Core concrete trace checking helpers

Supports generated proof obligations that reduce `traceSafeD` on concrete traces
to kernel decidable evaluation (`decide`).
-/

namespace PFCore

/-- Alias for generated proof scripts referencing trace safety decider. -/
abbrev traceSafeCheck (tr : Trace) : Bool := traceSafeD tr

theorem traceSafeCheck_eq (tr : Trace) : traceSafeCheck tr = traceSafeD tr := rfl

/-- Alias for generated per-event proof scripts. -/
abbrev eventSafeCheck (ev : Event) : Bool := eventSafeD ev

theorem eventSafeCheck_eq (ev : Event) : eventSafeCheck ev = eventSafeD ev := rfl

/-- Alias for generated handoff proof scripts. -/
abbrev handoffSafeCheck (h : Handoff) : Bool := handoffSafeD h

theorem handoffSafeCheck_eq (h : Handoff) : handoffSafeCheck h = handoffSafeD h := rfl

end PFCore
