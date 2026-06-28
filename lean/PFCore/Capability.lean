import PFCore.Catalog
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

/-- Closed PF-Core capability catalog (generated from schemas/pf_core.catalog.json). -/
def knownCatalogCaps : List String := Catalog.knownCatalogCaps

/-- Capability id is from the closed PF-Core catalog. -/
def KnownCapability (cap : String) : Prop :=
  cap ∈ knownCatalogCaps

/-- Boolean decider for ``KnownCapability``. -/
def knownCapabilityD (cap : String) : Bool :=
  cap ∈ knownCatalogCaps

/--
**Meaning:** The known-capability decider reflects catalog membership.

**Trusted use:** Soundness bridge for ``ActionAdmissible`` capability catalog checks.

**Does not imply:** Resource-pattern scope, runtime grant provenance, or delegated authority.
-/
theorem knownCapabilityD_sound (cap : String) :
    knownCapabilityD cap = true ↔ KnownCapability cap := by
  simp [knownCapabilityD, KnownCapability, decide_eq_true_iff]

end PFCore
