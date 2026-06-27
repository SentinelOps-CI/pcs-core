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

/-- Capability id is from the closed PF-Core catalog (mirrors Python ``CAPABILITY_CATALOG``). -/
def KnownCapability (cap : String) : Prop :=
  cap = "cap:file-read" ∨ cap = "cap:file-write" ∨ cap = "cap:network" ∨
    cap = "cap:email-send" ∨ cap = "cap:handoff" ∨ cap = "cap:mcp-invoke" ∨
    cap = "cap:lab-release"

/-- Boolean decider for ``KnownCapability``. -/
def knownCapabilityD (cap : String) : Bool :=
  cap = "cap:file-read" || cap = "cap:file-write" || cap = "cap:network" ||
    cap = "cap:email-send" || cap = "cap:handoff" || cap = "cap:mcp-invoke" ||
    cap = "cap:lab-release"

/--
**Meaning:** The known-capability decider reflects catalog membership.

**Trusted use:** Soundness bridge for ``ActionAdmissible`` capability catalog checks.

**Does not imply:** Resource-pattern scope, runtime grant provenance, or delegated authority.
-/
theorem knownCapabilityD_sound (cap : String) :
    knownCapabilityD cap = true ↔ KnownCapability cap := by
  unfold knownCapabilityD KnownCapability
  match cap with
  | "cap:file-read" => simp
  | "cap:file-write" => simp
  | "cap:network" => simp
  | "cap:email-send" => simp
  | "cap:handoff" => simp
  | "cap:mcp-invoke" => simp
  | "cap:lab-release" => simp
  | _ => simp

end PFCore
