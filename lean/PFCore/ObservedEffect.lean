import PFCore.EffectFrame
import PFCore.Hash
import PFCore.Transition

/-!
# PF-Core observed effects (runtime instrumentation model)

Declared action effects and effect frames constrain what a principal *may* do.
This module models **observed** effects attributed to an execution step by
runtime instrumentation or an external attestation.

## Claim separation (Workstream C1)

| Predicate | Meaning |
|-----------|---------|
| `ObservationSoundness` | Every observation agrees with the declared action footprint |
| `ObservationCompleteness` | Every frame-sensitive *actual* effect appears in observations |
| `EffectAttribution` | Observations are attributed to the given action (declared footprint) |
| `InstrumentationAuthenticity` | TCB / attestation assumption (not proved from untrusted logs) |
| `AttestedExecution` | Relates actual runtime effects to observed effects under authenticity |
| `TrustedInstrumentation` | Full attested-execution relation — **not** mere `ObservationsAgree` |

**Trusted-boundary assumption:** Observation faithfulness is only as strong as the
authenticity hypothesis. PF-Core does **not** prove that an untrusted producer
emitted complete observations. See `docs/pf-core/assumptions.md` and
`docs/pf-core/runtime-semantics.md`.
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
**Observation soundness:** Observed effects do not invent undeclared kinds/resources.
This is **not** trusted instrumentation by itself.
-/
def ObservationSoundness (a : Action) (obs : List ObservedEffect) : Prop :=
  ObservationsAgree a obs

/--
**Observation completeness:** Every frame-sensitive actual runtime effect appears
in the observation list (kind + resource). Requires a separate actual-effect record;
not discharged from observation lists alone.
-/
def ObservationCompleteness
    (actual : List ObservedEffect) (obs : List ObservedEffect) : Prop :=
  ∀ e ∈ actual, Effect.IsFrameSensitive e.kind →
    ∃ o ∈ obs, o.kind = e.kind ∧ o.resource = e.resource

/--
**Effect attribution:** Observations are attributed to action `a` (declared footprint).
Distinct from completeness over actual runtime effects.
-/
def EffectAttribution (a : Action) (obs : List ObservedEffect) : Prop :=
  ObservationsAgree a obs

/--
**Instrumentation authenticity:** Hypothesis discharged by runtime TCB or external
attestation. Boolean flag is an **assumption switch**, not a proved theorem.
-/
def InstrumentationAuthenticity (authenticated : Bool) : Prop :=
  authenticated = true

/--
Context connecting a declared action, observed effects, claimed actual effects, and
an authenticity hypothesis for attested execution.
-/
structure InstrumentationContext where
  action : Action
  observed : List ObservedEffect
  actual : List ObservedEffect
  /-- `true` only when TCB / attestation discharges authenticity. -/
  authenticated : Bool := false
deriving Repr

/--
**Attested execution relation:** actual runtime effects and observations agree under
soundness, completeness, attribution, and authenticity.
-/
def AttestedExecution (ctx : InstrumentationContext) : Prop :=
  ObservationSoundness ctx.action ctx.observed ∧
  ObservationCompleteness ctx.actual ctx.observed ∧
  EffectAttribution ctx.action ctx.observed ∧
  InstrumentationAuthenticity ctx.authenticated

/--
**Trusted instrumentation** is the attested-execution relation.

It is **definitionally distinct** from `ObservationsAgree` / `ObservationSoundness`.
Agreement alone never establishes trust.
-/
def TrustedInstrumentation (ctx : InstrumentationContext) : Prop :=
  AttestedExecution ctx

/-- Agreement / soundness is strictly weaker than trusted instrumentation. -/
theorem trusted_instrumentation_implies_observation_soundness
    (ctx : InstrumentationContext)
    (h : TrustedInstrumentation ctx) :
    ObservationSoundness ctx.action ctx.observed :=
  h.left

theorem trusted_instrumentation_implies_observations_agree
    (ctx : InstrumentationContext)
    (h : TrustedInstrumentation ctx) :
    ObservationsAgree ctx.action ctx.observed :=
  trusted_instrumentation_implies_observation_soundness ctx h

/--
Soundness alone does not imply authenticity. Counterexample shape: agreeing
observations with `authenticated = false` fail `TrustedInstrumentation`.
-/
theorem observation_soundness_not_trusted_without_authenticity
    (a : Action) (obs : List ObservedEffect)
    (_hSound : ObservationSoundness a obs) :
    ¬ TrustedInstrumentation
      { action := a, observed := obs, actual := obs, authenticated := false } := by
  intro hTrusted
  exact Bool.false_ne_true hTrusted.right.right.right

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

/-- Build an instrumentation context for an instrumented transition. -/
def InstrumentedTransition.toInstrumentationContext
    (it : InstrumentedTransition)
    (actual : List ObservedEffect)
    (authenticated : Bool) : InstrumentationContext :=
  { action := it.event.action
    observed := it.observations
    actual := actual
    authenticated := authenticated }

/--
**Meaning:** Under observation soundness, every observed effect kind is declared
on the action.

**Trusted use:** Bridging observation lists to declared `Action.effects`.

**Does not imply:** Completeness or authenticity (`TrustedInstrumentation`).
-/
theorem observation_soundness_kinds_declared
    (a : Action) (obs : List ObservedEffect)
    (hSound : ObservationSoundness a obs) :
    ∀ o ∈ obs, o.kind ∈ a.effects := by
  intro o hMem
  exact (hSound o hMem).left

/-- Compatibility name: kinds declared under soundness. -/
theorem trusted_instrumentation_kinds_declared
    (ctx : InstrumentationContext)
    (hInstr : TrustedInstrumentation ctx) :
    ∀ o ∈ ctx.observed, o.kind ∈ ctx.action.effects :=
  observation_soundness_kinds_declared ctx.action ctx.observed
    (trusted_instrumentation_implies_observation_soundness ctx hInstr)

/--
**Meaning:** Declared effects inside a frame imply observed sensitive kinds stay
in the frame when observations are sound wrt the declaration.

**Trusted use:** Undeclared-observation lemma for write/network/message/codeExecution/stateChange.

**Does not imply:** Completeness, authenticity, covert channels, or deny-path closure.
-/
theorem observed_sensitive_effects_in_frame
    (a : Action) (frame : List Effect) (obs : List ObservedEffect)
    (hSound : ObservationSoundness a obs)
    (hFrame : ActionEffectsInFrame a frame) :
    ∀ o ∈ obs, Effect.IsFrameSensitive o.kind → o.kind ∈ frame := by
  intro o hMem _hSens
  exact hFrame o.kind (observation_soundness_kinds_declared a obs hSound o hMem)

/--
**Meaning:** An accepted instrumented allow-transition cannot carry an observed
frame-sensitive effect absent from the declared effect frame, assuming observation
soundness (declared-footprint agreement).

**Trusted use:** Runtime attestation path should discharge full `TrustedInstrumentation`;
this lemma only needs soundness.

**Does not imply:** Completeness without authenticity, scheduler NI, or deny-path
side-effect freedom.
-/
theorem accepted_transition_no_undeclared_sensitive_observation
    (it : InstrumentedTransition) (frame : List Effect)
    (_hAcc : InstrumentedTransition.Accepted it)
    (hSound : ObservationSoundness it.event.action it.observations)
    (hFrame : ActionEffectsInFrame it.event.action frame) :
    ∀ o ∈ it.observations, Effect.IsFrameSensitive o.kind → o.kind ∈ frame :=
  observed_sensitive_effects_in_frame it.event.action frame it.observations hSound hFrame

/-- Attested-execution packaging of the undeclared-sensitive observation bound. -/
theorem attested_execution_no_undeclared_sensitive_observation
    (it : InstrumentedTransition) (frame : List Effect) (actual : List ObservedEffect)
    (hAcc : InstrumentedTransition.Accepted it)
    (hTrusted : TrustedInstrumentation
      (it.toInstrumentationContext actual true))
    (hFrame : ActionEffectsInFrame it.event.action frame) :
    ∀ o ∈ it.observations, Effect.IsFrameSensitive o.kind → o.kind ∈ frame :=
  accepted_transition_no_undeclared_sensitive_observation it frame hAcc
    (trusted_instrumentation_implies_observation_soundness
      (it.toInstrumentationContext actual true) hTrusted)
    hFrame

/-- Specialize: no observed write outside a write-free frame under sound observations. -/
theorem accepted_transition_no_undeclared_write_observation
    (it : InstrumentedTransition) (frame : List Effect)
    (hAcc : InstrumentedTransition.Accepted it)
    (hSound : ObservationSoundness it.event.action it.observations)
    (hFrame : ActionEffectsInFrame it.event.action frame)
    (hNoWrite : Effect.write ∉ frame) :
    ∀ o ∈ it.observations, o.kind = Effect.write → False := by
  intro o hMem hWrite
  have hin : Effect.write ∈ frame := by
    have hsens : Effect.IsFrameSensitive o.kind := by
      simp [hWrite, Effect.IsFrameSensitive]
    have := accepted_transition_no_undeclared_sensitive_observation
      it frame hAcc hSound hFrame o hMem hsens
    simpa [hWrite] using this
  exact hNoWrite hin

end PFCore
