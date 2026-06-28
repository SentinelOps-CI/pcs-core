import PFCore.ContractDecide
import PFCore.Handoff
import PFCore.NonInterference
import PFCore.Observational
import PFCore.ResourcePattern
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

/-- Alias for generated tenant-isolation proof scripts. -/
abbrev tenantIsolationCheck (tr : Trace) : Bool := tenantIsolationD tr

theorem tenantIsolationCheck_eq (tr : Trace) : tenantIsolationCheck tr = tenantIsolationD tr := rfl

/-- Alias for generated cross-tenant safety proof scripts. -/
abbrev traceCrossTenantSafeCheck (tr : Trace) : Bool := traceCrossTenantSafeD tr

theorem traceCrossTenantSafeCheck_eq (tr : Trace) :
    traceCrossTenantSafeCheck tr = traceCrossTenantSafeD tr := rfl

/-- Alias for generated observational non-interference proof scripts. -/
abbrev nonInterferenceCheck (tenantLow tenantHigh : String) (tr : Trace) : Bool :=
  nonInterferenceD tenantLow tenantHigh tr

theorem nonInterferenceCheck_eq (tenantLow tenantHigh : String) (tr : Trace) :
    nonInterferenceCheck tenantLow tenantHigh tr =
      nonInterferenceD tenantLow tenantHigh tr := rfl

/-- Alias for generated resource-pattern bridge proof scripts. -/
abbrev actionResourcesWithinCapabilityPatternCheck
    (reads writes : List Resource) (cap : String) : Bool :=
  actionResourcesWithinCapabilityPatternD reads writes cap

theorem actionResourcesWithinCapabilityPatternCheck_eq
    (reads writes : List Resource) (cap : String) :
    actionResourcesWithinCapabilityPatternCheck reads writes cap =
      actionResourcesWithinCapabilityPatternD reads writes cap := rfl

/-- Alias for generated resource-pattern trace safety proof scripts. -/
abbrev traceSafeRCheck (tr : Trace) : Bool := traceSafeRD tr

theorem traceSafeRCheck_eq (tr : Trace) : traceSafeRCheck tr = traceSafeRD tr := rfl

/-- Alias for generated resource-pattern event safety proof scripts. -/
abbrev eventSafeRCheck (ev : Event) : Bool := eventSafeRD ev

theorem eventSafeRCheck_eq (ev : Event) : eventSafeRCheck ev = eventSafeRD ev := rfl

end PFCore
