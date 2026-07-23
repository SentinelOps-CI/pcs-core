import PFCore.EffectFrame
import PFCore.Hash
import PFCore.Transition

/-!
# PF-Core observed effects (runtime instrumentation model)

Declared action effects and effect frames constrain what a principal *may* do.
This module models **observed** effects attributed to an execution step by
trusted runtime instrumentation or an external attestation.

**Trusted-boundary assumption:** Observation lists are faithful only when
`TrustedInstrumentation` (or an equivalent attestation) holds. PF-Core does
**not** prove that an untrusted producer emitted complete observations. See
`docs/pf-core/assumptions.md` and `docs/pf-core/runtime-semantics.md`.
-/

namespace PFCore

/-- One observed side effect attributed to a transition by instrumentation. -/
structure ObservedEffect where
  kind : Effect
  resource : Option Resource
  resultDigest : Option Hash
deriving Repr, DecidableEq

/-- Effect kinds whose undeclared observation would violate frame discipline. -/
def Effect.IsFrameSensitive : Effect → Prop
  | Effect.write | Effect.network | Effect.externalMessage
  | Effect.codeExecution | Effect.stateChange => True
  | Effect.read | Effect.custom _ => False

def effectIsFrameSensitiveD : Effect → Bool
  | Effect.write | Effect.network | Effect.externalMessage
  | Effect.codeExecution | Effect.stateChange => true
  | Effect.read | Effect.custom _ => false

theorem effectIsFrameSensitiveD_sound (e : Effect) :
    effectIsFrameSensitiveD e = true ↔ Effect.IsFrameSensitive e := by
  cases e <;> simp [effectIsFrameSensitiveD, Effect.IsFrameSensitive]

/-- Observed effect kind and optional resource lie within the declared action. -/
def ObservedEffectAgrees (a : Action) (o : ObservedEffect) : Prop :=
  o.kind ∈ a.effects ∧
    match o.resource with
    | none => True
    | some r => r ∈ a.reads ∨ r ∈ a.writes

def observedEffectAgreesD (a : Action) (o : ObservedEffect) : Bool :=
  decide (o.kind ∈ a.effects) &&
    match o.resource with
    | none => true
    | some r => decide (r ∈ a.reads ∨ r ∈ a.writes)

theorem observedEffectAgreesD_sound (a : Action) (o : ObservedEffect) :
    observedEffectAgreesD a o = true ↔ ObservedEffectAgrees a o := by
  cases o with
  | mk kind resource resultDigest =>
    cases resource with
    | none =>
      simp [observedEffectAgreesD, ObservedEffectAgrees, decide_eq_true_iff]
    | some r =>
      simp [observedEffectAgreesD, ObservedEffectAgrees, decide_eq_true_iff]

/-- Every observation agrees with the declared action footprint. -/
def ObservationsAgree (a : Action) (obs : List ObservedEffect) : Prop :=
  ∀ o ∈ obs, ObservedEffectAgrees a o

def observationsAgreeD (a : Action) (obs : List ObservedEffect) : Bool :=
  obs.all (fun o => observedEffectAgreesD a o)

theorem observationsAgreeD_sound (a : Action) (obs : List ObservedEffect) :
    observationsAgreeD a obs = true ↔ ObservationsAgree a obs := by
  simp [observationsAgreeD, ObservationsAgree, List.all_eq_true, observedEffectAgreesD_sound]

/--
**Assumption (trusted instrumentation / attestation):** Observations are a
faithful projection of actual effects for action `a`. This is **not** proved
from untrusted producer logs; it must be discharged by runtime TCB or
external attestation.
-/
def TrustedInstrumentation (a : Action) (obs : List ObservedEffect) : Prop :=
  ObservationsAgree a obs

/-- Instrumented operational step carrying observed effects. -/
structure InstrumentedTransition where
  pre : State
  post : State
  event : Event
  observations : List ObservedEffect
deriving Repr

/-- Accepted allow-step: decision allow, operational apply, and event safety. -/
def InstrumentedTransition.Accepted (it : InstrumentedTransition) : Prop :=
  it.event.decision = Decision.allow ∧
  Applies it.event it.pre it.post ∧
  EventSafe it.event

/--
**Meaning:** Under trusted instrumentation, every observed effect kind is declared
on the action.

**Trusted use:** Bridging observation lists to declared `Action.effects`.

**Does not imply:** Completeness of observations without `TrustedInstrumentation`.
-/
theorem trusted_instrumentation_kinds_declared
    (a : Action) (obs : List ObservedEffect)
    (hInstr : TrustedInstrumentation a obs) :
    ∀ o ∈ obs, o.kind ∈ a.effects := by
  intro o hMem
  exact (hInstr o hMem).left

/--
**Meaning:** Declared effects inside a frame imply observed sensitive kinds stay
in the frame when instrumentation is trusted.

**Trusted use:** Primary Phase 5.1 undeclared-observation lemma for
write/network/message/codeExecution/stateChange.

**Does not imply:** Uninstrumented runs, covert channels, or deny-path closure.
-/
theorem observed_sensitive_effects_in_frame
    (a : Action) (frame : List Effect) (obs : List ObservedEffect)
    (hInstr : TrustedInstrumentation a obs)
    (hFrame : ActionEffectsInFrame a frame) :
    ∀ o ∈ obs, Effect.IsFrameSensitive o.kind → o.kind ∈ frame := by
  intro o hMem _hSens
  exact hFrame o.kind (trusted_instrumentation_kinds_declared a obs hInstr o hMem)

/--
**Meaning:** An accepted instrumented allow-transition cannot carry an observed
frame-sensitive effect absent from the declared effect frame, assuming trusted
instrumentation.

**Trusted use:** Runtime attestation / instrumentation discharge for effect-frame
certificates.

**Does not imply:** Observations without attestation, scheduler NI, or deny-path
side-effect freedom.
-/
theorem accepted_transition_no_undeclared_sensitive_observation
    (it : InstrumentedTransition) (frame : List Effect)
    (_hAcc : InstrumentedTransition.Accepted it)
    (hInstr : TrustedInstrumentation it.event.action it.observations)
    (hFrame : ActionEffectsInFrame it.event.action frame) :
    ∀ o ∈ it.observations, Effect.IsFrameSensitive o.kind → o.kind ∈ frame :=
  observed_sensitive_effects_in_frame it.event.action frame it.observations hInstr hFrame

/-- Specialize: no observed write outside a write-free frame under instrumentation. -/
theorem accepted_transition_no_undeclared_write_observation
    (it : InstrumentedTransition) (frame : List Effect)
    (hAcc : InstrumentedTransition.Accepted it)
    (hInstr : TrustedInstrumentation it.event.action it.observations)
    (hFrame : ActionEffectsInFrame it.event.action frame)
    (hNoWrite : Effect.write ∉ frame) :
    ∀ o ∈ it.observations, o.kind = Effect.write → False := by
  intro o hMem hWrite
  have hin : Effect.write ∈ frame := by
    have hsens : Effect.IsFrameSensitive o.kind := by
      simp [hWrite, Effect.IsFrameSensitive]
    have := accepted_transition_no_undeclared_sensitive_observation
      it frame hAcc hInstr hFrame o hMem hsens
    simpa [hWrite] using this
  exact hNoWrite hin

end PFCore
