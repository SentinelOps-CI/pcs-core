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

/--
**Meaning:** The boolean `hasCapabilityD` decider reflects capability list membership.

**Trusted use:** Soundness bridge for action allowance and contract preconditions.

**Does not imply:** Role expansion, runtime grant provenance, or delegated authority validity.
-/
theorem hasCapabilityD_sound (p : Principal) (cap : String) :
    hasCapabilityD p cap = true ↔ HasCapability p cap := by
  simp [hasCapabilityD, HasCapability, decide_eq_true_iff]

end PFCore
