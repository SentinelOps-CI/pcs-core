import PFCore.Contract

/-!
# PF-Core JSON contract deciders

Decidable mirrors of `PFCoreContract.v0` pre/post/invariant fields used by
generated concrete proof obligations. Soundness theorems link deciders to
conservative Prop-level contract satisfaction.
-/

namespace PFCore

/-- JSON contract preconditions (subset discharged in Lean). -/
structure ContractPreSpec where
  requireCapability : Option String := none
  requireEffect : Option Effect := none
  requireTenantMatch : Bool := false
deriving Repr

/-- JSON contract postconditions (subset discharged in Lean). -/
structure ContractPostSpec where
  requireDecision : Option Decision := none
  requireEventSafe : Bool := false
deriving Repr

/-- JSON contract trace invariant (subset discharged in Lean). -/
structure ContractInvariantSpec where
  requireTraceSafe : Bool := false
deriving Repr

def actionHasEffect (a : Action) (e : Effect) : Prop := e ∈ a.effects

def actionHasEffectD (a : Action) (e : Effect) : Bool := decide (e ∈ a.effects)

/--
**Meaning:** Effect membership decider reflects `actionHasEffect`.

**Trusted use:** Contract preconditions requiring specific effects.

**Does not imply:** Effect execution occurred or was authorized at runtime.
-/
theorem actionHasEffectD_sound (a : Action) (e : Effect) :
    actionHasEffectD a e = true ↔ actionHasEffect a e := by
  simp [actionHasEffectD, actionHasEffect, decide_eq_true_iff]

def contractPreD (spec : ContractPreSpec) (p : Principal) (a : Action) : Bool :=
  let capOk := match spec.requireCapability with
    | none => true
    | some cap => hasCapabilityD p cap
  let effectOk := match spec.requireEffect with
    | none => true
    | some eff => actionHasEffectD a eff
  let tenantOk := if spec.requireTenantMatch then actionWithinTenantD p a else true
  capOk && effectOk && tenantOk

def ContractPreHolds (spec : ContractPreSpec) (p : Principal) (a : Action) : Prop :=
  (match spec.requireCapability with
    | none => True
    | some cap => HasCapability p cap) ∧
  (match spec.requireEffect with
    | none => True
    | some eff => actionHasEffect a eff) ∧
    (if spec.requireTenantMatch then ActionWithinTenant p a else True)

/--
**Meaning:** JSON contract pre decider reflects conservative `ContractPreHolds`.

**Trusted use:** Generated `concrete_contract_pre_*` proof soundness.

**Does not imply:** Unmapped JSON pre fields (`require_role`, refs) hold.
-/
theorem contractPreD_sound (spec : ContractPreSpec) (p : Principal) (a : Action) :
    contractPreD spec p a = true ↔ ContractPreHolds spec p a := by
  rcases spec with ⟨cap, eff, tenant⟩
  unfold contractPreD ContractPreHolds
  cases cap <;> cases eff <;> cases tenant <;>
    simp [hasCapabilityD_sound, actionHasEffectD_sound, actionWithinTenantD_sound,
      decide_eq_true_iff, and_left_comm, and_assoc]

def contractPostD (spec : ContractPostSpec) (ev : Event) : Bool :=
  let decisionOk := match spec.requireDecision with
    | none => true
    | some d => decide (ev.decision = d)
  let safeOk := if spec.requireEventSafe then eventSafeD ev else true
  decisionOk && safeOk

def ContractPostHolds (spec : ContractPostSpec) (ev : Event) : Prop :=
  (match spec.requireDecision with
    | none => True
    | some d => ev.decision = d) ∧
  (if spec.requireEventSafe then EventSafe ev else True)

/--
**Meaning:** JSON contract post decider reflects conservative `ContractPostHolds`.

**Trusted use:** Generated `concrete_contract_post_*` proof soundness.

**Does not imply:** Full PFCoreContract.v0 post semantics beyond mapped fields.
-/
theorem contractPostD_sound (spec : ContractPostSpec) (ev : Event) :
    contractPostD spec ev = true ↔ ContractPostHolds spec ev := by
  rcases spec with ⟨reqDec, reqSafe⟩
  cases ev with
  | mk id p a d =>
    cases d <;> cases reqDec <;> cases reqSafe <;>
      simp [contractPostD, ContractPostHolds, EventSafe, eventSafeD, eventSafeD_sound,
        actionAllowedD_sound, decide_eq_true_iff, Bool.and_eq_true, if_true, if_false]

def contractInvariantD (spec : ContractInvariantSpec) (tr : Trace) : Bool :=
  if spec.requireTraceSafe then traceSafeD tr else true

def ContractInvariantHolds (spec : ContractInvariantSpec) (tr : Trace) : Prop :=
  if spec.requireTraceSafe then TraceSafe tr else True

/--
**Meaning:** JSON contract invariant decider reflects `ContractInvariantHolds`.

**Trusted use:** Generated `concrete_trace_satisfies_*` invariant discharge.

**Does not imply:** Custom invariants or unmapped contract fields hold.
-/
theorem contractInvariantD_sound (spec : ContractInvariantSpec) (tr : Trace) :
    contractInvariantD spec tr = true ↔ ContractInvariantHolds spec tr := by
  rcases spec with ⟨reqSafe⟩
  cases reqSafe <;> simp [contractInvariantD, ContractInvariantHolds, traceSafeD_sound]

def satisfiesContractSpecD (pre : ContractPreSpec) (post : ContractPostSpec) (ev : Event) : Bool :=
  contractPreD pre ev.principal ev.action && contractPostD post ev

def SatisfiesContractSpec (pre : ContractPreSpec) (post : ContractPostSpec) (ev : Event) : Prop :=
  ContractPreHolds pre ev.principal ev.action ∧ ContractPostHolds post ev

/--
**Meaning:** Per-event contract spec decider reflects `SatisfiesContractSpec`.

**Trusted use:** Generated `concrete_satisfies_*` theorems.

**Does not imply:** Trace-wide or sequential contract composition automatically.
-/
theorem satisfiesContractSpecD_sound (pre : ContractPreSpec) (post : ContractPostSpec) (ev : Event) :
    satisfiesContractSpecD pre post ev = true ↔ SatisfiesContractSpec pre post ev := by
  simp [satisfiesContractSpecD, SatisfiesContractSpec, contractPreD_sound, contractPostD_sound,
    and_left_comm]

def traceSatisfiesContractSpecsD (pre : ContractPreSpec) (post : ContractPostSpec)
    (inv : ContractInvariantSpec) : Trace → Bool
  | Trace.empty => true
  | Trace.cons tr ev =>
    traceSatisfiesContractSpecsD pre post inv tr &&
    satisfiesContractSpecD pre post ev &&
    contractInvariantD inv (Trace.cons tr ev)

def TraceSatisfiesContractSpecs (pre : ContractPreSpec) (post : ContractPostSpec)
    (inv : ContractInvariantSpec) : Trace → Prop
  | Trace.empty => True
  | Trace.cons tr ev =>
    TraceSatisfiesContractSpecs pre post inv tr ∧
    SatisfiesContractSpec pre post ev ∧
    ContractInvariantHolds inv (Trace.cons tr ev)

/--
**Meaning:** Trace-level contract spec decider reflects `TraceSatisfiesContractSpecs`.

**Trusted use:** Generated trace-wide contract satisfaction proofs.

**Does not imply:** Runtime-only contract fields or missing contract JSON are discharged.
-/
theorem traceSatisfiesContractSpecsD_sound (pre : ContractPreSpec) (post : ContractPostSpec)
    (inv : ContractInvariantSpec) (tr : Trace) :
    traceSatisfiesContractSpecsD pre post inv tr = true ↔
      TraceSatisfiesContractSpecs pre post inv tr := by
  induction tr with
  | empty =>
    cases inv with
    | mk reqSafe =>
      cases reqSafe <;> simp [traceSatisfiesContractSpecsD, TraceSatisfiesContractSpecs,
        contractInvariantD_sound]
  | cons tr' ev ih =>
    cases inv with
    | mk reqSafe =>
      cases reqSafe <;>
        simp [traceSatisfiesContractSpecsD, TraceSatisfiesContractSpecs, ih,
          satisfiesContractSpecD_sound, contractInvariantD_sound, and_assoc, and_left_comm]

end PFCore
