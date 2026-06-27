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

/--
**Meaning:** `traceSafeCheck` is definitionally equal to `traceSafeD`.

**Trusted use:** Stable alias name in generated proof scripts.

**Does not imply:** Additional safety properties beyond `traceSafeD`.
-/
theorem traceSafeCheck_eq (tr : Trace) : traceSafeCheck tr = traceSafeD tr := rfl

/-- Alias for generated per-event proof scripts. -/
abbrev eventSafeCheck (ev : Event) : Bool := eventSafeD ev

/--
**Meaning:** `eventSafeCheck` is definitionally equal to `eventSafeD`.

**Trusted use:** Stable alias name in generated per-event proof scripts.

**Does not imply:** Additional safety properties beyond `eventSafeD`.
-/
theorem eventSafeCheck_eq (ev : Event) : eventSafeCheck ev = eventSafeD ev := rfl

/-- Alias for generated handoff proof scripts. -/
abbrev handoffSafeCheck (h : Handoff) : Bool := handoffSafeD h

/--
**Meaning:** `handoffSafeCheck` is definitionally equal to `handoffSafeD`.

**Trusted use:** Stable alias name in generated handoff proof scripts.

**Does not imply:** Additional safety properties beyond `handoffSafeD`.
-/
theorem handoffSafeCheck_eq (h : Handoff) : handoffSafeCheck h = handoffSafeD h := rfl

end PFCore
