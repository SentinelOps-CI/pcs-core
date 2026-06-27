import PFCore.Principal

/-!
# PF-Core resources and tenant alignment
-/

namespace PFCore

/-- Addressable resource scoped to a tenant. -/
structure Resource where
  uri : String
  tenant : String
  labels : List String
deriving Repr, DecidableEq

/-- Resource `r` is visible to principal `p` when tenants match. -/
def SameTenantResource (p : Principal) (r : Resource) : Prop :=
  p.tenant = r.tenant

/-- Boolean decider for `SameTenantResource`. -/
def sameTenantResourceD (p : Principal) (r : Resource) : Bool :=
  p.tenant == r.tenant

/--
**Meaning:** Tenant string equality between principal and resource is decidable and sound.

**Trusted use:** Building blocks for action tenant checks and non-interference lemmas.

**Does not imply:** Label-based access control or URI normalization correctness.
-/
theorem sameTenantResourceD_sound (p : Principal) (r : Resource) :
    sameTenantResourceD p r = true ↔ SameTenantResource p r := by
  simp [sameTenantResourceD, SameTenantResource, BEq.beq]

/-- Every resource in `rs` shares principal `p`'s tenant. -/
def allResourcesSameTenant (p : Principal) (rs : List Resource) : Prop :=
  ∀ r ∈ rs, SameTenantResource p r

def resourcesSameTenantD (p : Principal) (rs : List Resource) : Bool :=
  rs.all fun r => sameTenantResourceD p r

/--
**Meaning:** List tenant decider reflects universal tenant alignment over resources.

**Trusted use:** Action read/write footprint validation in allowance deciders.

**Does not imply:** Resource existence, reachability, or side-channel isolation.
-/
theorem resourcesSameTenantD_sound (p : Principal) (rs : List Resource) :
    resourcesSameTenantD p rs = true ↔ allResourcesSameTenant p rs := by
  simp [resourcesSameTenantD, allResourcesSameTenant, sameTenantResourceD_sound, List.all_eq_true]

end PFCore
