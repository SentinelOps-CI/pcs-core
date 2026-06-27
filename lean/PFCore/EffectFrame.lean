import PFCore.Action
import PFCore.Transition

/-!
# PF-Core effect frames

Effect frames constrain declared action effects. When an action's effects stay within
a frame that excludes `Effect.write`, no write footprint is declared on any resource
provided write resources imply the write effect (see `WriteFootprintRequiresWriteEffect`).
-/

namespace PFCore

/-- Effect `eff` is permitted within effect frame `frame`. -/
def EffectAllowedInFrame (eff : Effect) (frame : List Effect) : Prop :=
  eff ∈ frame

/-- Every declared effect on action `a` lies in effect frame `frame`. -/
def ActionEffectsInFrame (a : Action) (frame : List Effect) : Prop :=
  ∀ e ∈ a.effects, EffectAllowedInFrame e frame

def effectAllowedInFrameD (eff : Effect) (frame : List Effect) : Bool :=
  decide (eff ∈ frame)

def actionEffectsInFrameD (a : Action) (frame : List Effect) : Bool :=
  a.effects.all (fun e => effectAllowedInFrameD e frame)

/--
**Meaning:** Effect-in-frame decider reflects `EffectAllowedInFrame`.

**Trusted use:** Generated effect-frame discharge and runtime alignment.

**Does not imply:** Effects were executed or authorized beyond declaration.
-/
theorem effectAllowedInFrameD_sound (eff : Effect) (frame : List Effect) :
    effectAllowedInFrameD eff frame = true ↔ EffectAllowedInFrame eff frame := by
  simp [effectAllowedInFrameD, EffectAllowedInFrame, decide_eq_true_iff]

/--
**Meaning:** Action effect-frame decider reflects `ActionEffectsInFrame`.

**Trusted use:** Whole-action effect frame checks in certificates.

**Does not imply:** Resource-level policy beyond declared action footprint.
-/
theorem actionEffectsInFrameD_sound (a : Action) (frame : List Effect) :
    actionEffectsInFrameD a frame = true ↔ ActionEffectsInFrame a frame := by
  simp [actionEffectsInFrameD, ActionEffectsInFrame, EffectAllowedInFrame,
    List.all_eq_true, effectAllowedInFrameD_sound, decide_eq_true_iff]

/-- Action is admissible relative to an effect frame. -/
def EffectFrameAdmissible (a : Action) (frame : List Effect) : Prop :=
  ActionEffectsInFrame a frame

def effectFrameAdmissibleD (a : Action) (frame : List Effect) : Bool :=
  actionEffectsInFrameD a frame

/--
**Meaning:** Effect-frame admissibility decider reflects `EffectFrameAdmissible`.

**Trusted use:** Bridging deciders to Prop-level effect frame obligations.

**Does not imply:** Capability, tenant, or trace safety without separate checks.
-/
theorem effectFrameAdmissibleD_sound (a : Action) (frame : List Effect) :
    effectFrameAdmissibleD a frame = true ↔ EffectFrameAdmissible a frame := by
  simp [effectFrameAdmissibleD, EffectFrameAdmissible, actionEffectsInFrameD_sound]

/-- Non-empty write footprint implies the write effect is declared on the action. -/
def WriteFootprintRequiresWriteEffect (a : Action) : Prop :=
  ∀ r ∈ a.writes, Effect.write ∈ a.effects

/--
**Meaning:** Effect frame excluding write forbids declaring the write effect.

**Trusted use:** First step of undeclared-write prevention on resources.

**Does not imply:** Empty `writes` list or runtime write suppression.
-/
theorem effect_frame_excludes_write_effect (a : Action) (frame : List Effect) :
    ActionEffectsInFrame a frame → Effect.write ∉ frame → Effect.write ∉ a.effects := by
  intro hframe hno hmem
  exact hno (hframe Effect.write hmem)

/--
**Meaning:** With aligned write footprint, a write-free effect frame implies no writes on `R`.

**Trusted use:** Primary undeclared-write lemma for resource `R`.

**Does not imply:** Covert channels, runtime enforcement, or per-resource effect labels.
-/
theorem effect_frame_prevents_undeclared_writes (a : Action) (frame : List Effect) (r : Resource) :
    ActionEffectsInFrame a frame → Effect.write ∉ frame → WriteFootprintRequiresWriteEffect a →
    r ∉ a.writes := by
  intro hframe hno halign hmem
  have hwrite := halign r hmem
  exact absurd hwrite (effect_frame_excludes_write_effect a frame hframe hno)

/--
**Meaning:** `ActionAdmissible` with write footprint alignment links to `ActionAllowed` effect membership.

**Trusted use:** Composing effect frames with allowance predicates.

**Does not imply:** Automatic trace or contract satisfaction.
-/
theorem actionEffectsInFrame_of_admissible (p : Principal) (a : Action) (frame : List Effect) :
    ActionAdmissible p a → ActionEffectsInFrame a frame → EffectFrameAdmissible a frame := by
  intro _ h
  exact h

/--
**Meaning:** `ActionAllowed` is `ActionAdmissible`; effect-frame checks compose with allowance.

**Trusted use:** Link to `ActionAllowed` / `ActionAdmissible` in certificates.

**Does not imply:** Write footprint alignment unless explicitly assumed.
-/
theorem actionAllowed_effect_frame (p : Principal) (a : Action) (frame : List Effect) :
    ActionAllowed p a → ActionEffectsInFrame a frame → EffectFrameAdmissible a frame :=
  actionEffectsInFrame_of_admissible p a frame

/--
**Meaning:** Admissible actions declare all effects within their own effect list (reflexive frame).

**Trusted use:** Base case linking admissibility to effect membership.

**Does not imply:** External effect frame policy was checked.
-/
theorem actionAdmissible_effects_in_self (p : Principal) (a : Action) :
    ActionAdmissible p a → ActionEffectsInFrame a a.effects := by
  intro _ e he
  exact he

/--
**Meaning:** File-write capability actions align write footprint with write effect declaration.

**Trusted use:** Discharging `WriteFootprintRequiresWriteEffect` for catalog file-write actions.

**Does not imply:** All tool mappings enforce this alignment without runtime validation.
-/
theorem file_write_capability_aligns_write_footprint (p : Principal) (a : Action) (r : Resource) :
    ActionAdmissible p a → a.capability = "cap:file-write" → r ∈ a.writes →
    Effect.write ∈ a.effects := by
  intro hAdm _ hmem
  exact hAdm.right.right.right

end PFCore
