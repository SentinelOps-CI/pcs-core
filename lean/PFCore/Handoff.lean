import PFCore.Capability

/-!
# PF-Core capability handoff (non-expanding delegation)
-/

namespace PFCore

/-- Delegation of capabilities from one principal to another. -/
structure Handoff where
  fromPrincipal : Principal
  toPrincipal : Principal
  delegatedCapabilities : List String

/-- Every capability in `xs` is also listed in `ys`. -/
def CapabilitySubset (xs ys : List String) : Prop :=
  ∀ x, x ∈ xs → x ∈ ys

def capabilitySubsetD (xs ys : List String) : Bool :=
  xs.all fun x => decide (x ∈ ys)

theorem capabilitySubsetD_sound (xs ys : List String) :
    capabilitySubsetD xs ys = true ↔ CapabilitySubset xs ys := by
  simp [capabilitySubsetD, CapabilitySubset, List.all_eq_true, decide_eq_true_iff]

/-- Handoff is safe when delegation is a subset and tenants match. -/
def HandoffSafe (h : Handoff) : Prop :=
  CapabilitySubset h.delegatedCapabilities h.fromPrincipal.capabilities ∧
  h.fromPrincipal.tenant = h.toPrincipal.tenant

def handoffSafeD (h : Handoff) : Bool :=
  capabilitySubsetD h.delegatedCapabilities h.fromPrincipal.capabilities &&
    decide (h.fromPrincipal.tenant = h.toPrincipal.tenant)

theorem handoffSafeD_sound (h : Handoff) :
    handoffSafeD h = true ↔ HandoffSafe h := by
  simp [handoffSafeD, HandoffSafe, capabilitySubsetD_sound, decide_eq_true_iff]

/-- Safe handoff never grants a capability absent from the source principal. -/
theorem handoff_does_not_expand_authority (h : Handoff) (cap : String) :
    HandoffSafe h → cap ∈ h.delegatedCapabilities → HasCapability h.fromPrincipal cap := by
  intro hsafe hmem
  exact hsafe.left cap hmem

end PFCore
