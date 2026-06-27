import PFCore.Capability
import PFCore.Resource

/-!
# PF-Core actions and allowance predicates
-/

namespace PFCore

/-- Effect kinds for tool actions (closed enum plus custom labels). -/
inductive Effect where
  | read | write | network | externalMessage | codeExecution | stateChange
  | custom : String → Effect
deriving Repr, DecidableEq

/-- Tool invocation with capability requirement and resource footprint. -/
structure Action where
  id : String
  toolName : String
  capability : String
  effects : List Effect
  reads : List Resource
  writes : List Resource
deriving Repr, DecidableEq

/-- All read/write resources belong to principal `p`'s tenant. -/
def ActionWithinTenant (p : Principal) (a : Action) : Prop :=
  allResourcesSameTenant p a.reads ∧ allResourcesSameTenant p a.writes

def actionWithinTenantD (p : Principal) (a : Action) : Bool :=
  resourcesSameTenantD p a.reads && resourcesSameTenantD p a.writes

/--
**Meaning:** The tenant decider matches in-tenant resource footprint for reads and writes.

**Trusted use:** Tenant isolation checks aligned with runtime `validate_resource_scope`.

**Does not imply:** Cross-tenant denial correctness or network egress safety.
-/
theorem actionWithinTenantD_sound (p : Principal) (a : Action) :
    actionWithinTenantD p a = true ↔ ActionWithinTenant p a := by
  simp [actionWithinTenantD, ActionWithinTenant, resourcesSameTenantD_sound, and_left_comm]

/-- Action is allowed when capability is held and resources stay in-tenant. -/
def ActionAllowed (p : Principal) (a : Action) : Prop :=
  HasCapability p a.capability ∧ ActionWithinTenant p a

def actionAllowedD (p : Principal) (a : Action) : Bool :=
  hasCapabilityD p a.capability && actionWithinTenantD p a

/--
**Meaning:** The combined action decider reflects capability plus tenant-scoped resources.

**Trusted use:** Core allowance predicate for `EventSafe` and generated concrete proofs.

**Does not imply:** Effect-level policy, contract postconditions, or external checker claims.
-/
theorem actionAllowedD_sound (p : Principal) (a : Action) :
    actionAllowedD p a = true ↔ ActionAllowed p a := by
  simp [actionAllowedD, ActionAllowed, hasCapabilityD_sound, actionWithinTenantD_sound, and_left_comm]

end PFCore
