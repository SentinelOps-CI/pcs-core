import PFCore.Capability
import PFCore.Catalog
import PFCore.Effect
import PFCore.Resource

/-!
# PF-Core actions and allowance predicates
-/

namespace PFCore

/-- Tool invocation with capability requirement and resource footprint. -/
structure Action where
  id : String
  toolName : String
  capability : String
  capabilityEffect : Effect
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

/-- Effect is from the closed PF-Core catalog (custom only for documented labels). -/
def EffectKnown (e : Effect) : Prop :=
  match e with
  | Effect.custom label => label ∈ Catalog.knownCustomEffectLabels
  | _ => True

def effectKnownD : Effect → Bool
  | Effect.custom label => decide (label ∈ Catalog.knownCustomEffectLabels)
  | _ => true

theorem effectKnownD_sound (e : Effect) : effectKnownD e = true ↔ EffectKnown e := by
  cases e <;> simp [effectKnownD, EffectKnown, decide_eq_true_iff]

/-- Every declared action effect is catalog-known. -/
def ActionEffectsKnown (a : Action) : Prop :=
  ∀ e ∈ a.effects, EffectKnown e

def actionEffectsKnownD (a : Action) : Bool :=
  a.effects.all effectKnownD

theorem actionEffectsKnownD_sound (a : Action) :
    actionEffectsKnownD a = true ↔ ActionEffectsKnown a := by
  simp [actionEffectsKnownD, ActionEffectsKnown, List.all_eq_true, effectKnownD_sound]

/-- Embedded capability effect appears in the action effect list. -/
def CapabilityMatchesEffects (a : Action) : Prop :=
  a.capabilityEffect ∈ a.effects

def capabilityMatchesEffectsD (a : Action) : Bool :=
  decide (a.capabilityEffect ∈ a.effects)

theorem capabilityMatchesEffectsD_sound (a : Action) :
    capabilityMatchesEffectsD a = true ↔ CapabilityMatchesEffects a := by
  simp [capabilityMatchesEffectsD, CapabilityMatchesEffects, decide_eq_true_iff]

/-- Catalog pairs mapping capability ids to canonical embedded effects (generated). -/
def knownCapabilityEffectCatalog : List (String × Effect) :=
  Catalog.knownCapabilityEffectCatalog

/-- Catalog capability id maps to its canonical embedded effect label. -/
def KnownCapabilityEffect (cap : String) (eff : Effect) : Prop :=
  (cap, eff) ∈ knownCapabilityEffectCatalog

/-- Boolean decider for ``KnownCapabilityEffect``. -/
def knownCapabilityEffectD (cap : String) (eff : Effect) : Bool :=
  decide ((cap, eff) ∈ knownCapabilityEffectCatalog)

/--
**Meaning:** The capability-effect decider reflects ``KnownCapabilityEffect``.

**Trusted use:** Linking embedded ``capabilityEffect`` to catalog effect labels in admissibility.

**Does not imply:** Runtime effect execution or resource-pattern enforcement.
-/
theorem knownCapabilityEffectD_sound (cap : String) (eff : Effect) :
    knownCapabilityEffectD cap eff = true ↔ KnownCapabilityEffect cap eff := by
  simp [knownCapabilityEffectD, KnownCapabilityEffect, decide_eq_true_iff]

/--
**Meaning:** File-write catalog capability embeds ``Effect.write``.

**Trusted use:** Discharging write-effect membership from admissibility for file-write actions.

**Does not imply:** Write footprint alignment or runtime write suppression.
-/
theorem knownCapabilityEffect_file_write (cap : String) (eff : Effect) :
    cap = "cap:file-write" → KnownCapabilityEffect cap eff → eff = Effect.write := by
  intro hcap h
  simp [KnownCapabilityEffect, knownCapabilityEffectCatalog, Catalog.knownCapabilityEffectCatalog, hcap] at h
  exact h

/-- Structural action preconditions before allowance. -/
def ActionAdmissible (p : Principal) (a : Action) : Prop :=
  HasCapability p a.capability ∧
    ActionWithinTenant p a ∧
    ActionEffectsKnown a ∧
    CapabilityMatchesEffects a ∧
    KnownCapability a.capability ∧
    KnownCapabilityEffect a.capability a.capabilityEffect

def actionAdmissibleD (p : Principal) (a : Action) : Bool :=
  hasCapabilityD p a.capability &&
    actionWithinTenantD p a &&
    actionEffectsKnownD a &&
    capabilityMatchesEffectsD a &&
    knownCapabilityD a.capability &&
    knownCapabilityEffectD a.capability a.capabilityEffect

theorem actionAdmissibleD_sound (p : Principal) (a : Action) :
    actionAdmissibleD p a = true ↔ ActionAdmissible p a := by
  unfold actionAdmissibleD ActionAdmissible
  simp [hasCapabilityD_sound, actionWithinTenantD_sound, actionEffectsKnownD_sound,
    capabilityMatchesEffectsD_sound, knownCapabilityD_sound, knownCapabilityEffectD_sound,
    Bool.and_eq_true, and_assoc, and_left_comm, and_comm]

/-- Action is allowed when capability is held and structural checks pass. -/
def ActionAllowed (p : Principal) (a : Action) : Prop :=
  ActionAdmissible p a

def actionAllowedD (p : Principal) (a : Action) : Bool :=
  actionAdmissibleD p a

/--
**Meaning:** The combined action decider reflects capability, tenant, effect catalog, and capability/effect alignment.

**Trusted use:** Core allowance predicate for `EventSafe` and generated concrete proofs.

**Does not imply:** Effect-level policy, contract postconditions, or external checker claims.
-/
theorem actionAllowedD_sound (p : Principal) (a : Action) :
    actionAllowedD p a = true ↔ ActionAllowed p a := by
  exact actionAdmissibleD_sound p a

end PFCore
