import PFCore.Principal

/-!
# PF-Core capability membership
-/

namespace PFCore

/-- Principal `p` holds capability name `cap` when `cap` appears in `p.capabilities`. -/
def HasCapability (p : Principal) (cap : String) : Prop :=
  cap ∈ p.capabilities

/-- Boolean decider for `HasCapability`. -/
def hasCapabilityD (p : Principal) (cap : String) : Bool :=
  decide (cap ∈ p.capabilities)

/-- `hasCapabilityD` reflects `HasCapability` (soundness). -/
theorem hasCapabilityD_sound (p : Principal) (cap : String) :
    hasCapabilityD p cap = true ↔ HasCapability p cap := by
  simp [hasCapabilityD, HasCapability, decide_eq_true_iff]

end PFCore
