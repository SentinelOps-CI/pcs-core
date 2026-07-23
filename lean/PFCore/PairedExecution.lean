import PFCore.Observational
import PFCore.Transition

/-!
# PF-Core paired-execution non-interference (research scaffolding)

**Status:** Research scaffolding only. Strong paired-execution non-interference
theorems are **not proved** here and must **not** be cited as release claims.

The proved single-trace observational property is `TenantProjectionIsolation`
(see `Observational.lean`). Reserve the name **NonInterference** for a future
paired-execution theorem family in a later schema/kernel version.

This module records vocabulary and assumptions required for that future family:
paired executions, low-equivalent initial states, high-input perturbations,
an explicit scheduler model, low-output equivalence, termination and timing
assumptions, and declassification rules.
-/

namespace PFCore

/-- One recorded execution: initial state, event trace, and final state. -/
structure Execution where
  initial : State
  trace : Trace
  finalState : State
deriving Repr

/--
Abstract scheduler model. In v0 the recorded `Trace` already fixes event order;
a future scheduler adversary would quantify over reorderings of high events.
-/
structure Scheduler where
  /-- Documentation tag; scheduler policies are not discharged in v0. -/
  label : String := "trace-recorded"
deriving Repr, DecidableEq

/-- Low-equivalent resource frames for observer `tenantLow`. -/
def LowEquivalentResourceFrames (tenantLow : String)
    (f1 f2 : List Resource) : Prop :=
  (f1.filter (fun r => r.tenant = tenantLow)) =
    (f2.filter (fun r => r.tenant = tenantLow))

/-- Low-equivalent initial states for observer `tenantLow`. -/
def LowEquivalentStates (tenantLow : String) (s1 s2 : State) : Prop :=
  s1.tenant = s2.tenant ∧
  (s1.tenant = tenantLow →
    LowEquivalentResourceFrames tenantLow s1.resourceFrame s2.resourceFrame ∧
      s1.capabilityFrame = s2.capabilityFrame)

/-- High-input perturbation: executions may differ on high-tenant events. -/
def HighInputPerturbation (tenantHigh : String) (e1 e2 : Execution) : Prop :=
  (∀ ev, EventIn ev e1.trace → HighTenantEvent tenantHigh ev → True) ∧
  (∀ ev, EventIn ev e2.trace → HighTenantEvent tenantHigh ev → True)

/-- Low-output equivalence: matching tenant projections. -/
def LowOutputEquivalent (tenantLow : String) (e1 e2 : Execution) : Prop :=
  TraceProjection tenantLow e1.trace = TraceProjection tenantLow e2.trace ∧
  LowEquivalentStates tenantLow e1.finalState e2.finalState

/-- Explicit declassification rule label (future policy hook). -/
structure DeclassificationRule where
  id : String
  description : String := ""
deriving Repr, DecidableEq

/--
Assumptions required before any paired-execution NI claim can be stated.
Boolean flags are **assumption switches**, not theorems.
-/
structure PairedExecutionAssumptions where
  /-- Observations / traces are complete under trusted instrumentation or attestation. -/
  trustedInstrumentation : Bool := true
  /-- Both executions terminate. -/
  termination : Bool := true
  /-- Timing channels are out of the observation model (or bounded). -/
  timingIndependent : Bool := true
  /-- Scheduler is within the declared `Scheduler` model. -/
  schedulerModel : Scheduler := { label := "trace-recorded" }
  /-- Optional declassification policy (empty = none). -/
  declassification : List DeclassificationRule := []
deriving Repr

/--
**Research target (unproved):** Paired-execution non-interference under the
stated assumptions. Defined so obligations can be named without claiming a proof.

Do **not** treat inhabitance of this Prop as evidence of NI for arbitrary systems.
-/
def PairedExecutionNonInterference
    (tenantLow tenantHigh : String)
    (e1 e2 : Execution)
    (asm : PairedExecutionAssumptions) : Prop :=
  asm.trustedInstrumentation = true →
  asm.termination = true →
  asm.timingIndependent = true →
  LowEquivalentStates tenantLow e1.initial e2.initial →
  HighInputPerturbation tenantHigh e1 e2 →
  LowOutputEquivalent tenantLow e1 e2

/-- Reflexivity of low-output equivalence on a single execution. -/
theorem low_output_equivalent_refl (tenantLow : String) (e : Execution) :
    LowOutputEquivalent tenantLow e e := by
  refine ⟨rfl, ?_⟩
  refine ⟨rfl, ?_⟩
  intro _
  exact ⟨rfl, rfl⟩

/-- Reflexivity of low-equivalent states. -/
theorem low_equivalent_states_refl (tenantLow : String) (s : State) :
    LowEquivalentStates tenantLow s s := by
  refine ⟨rfl, ?_⟩
  intro _
  exact ⟨rfl, rfl⟩

/--
Same-trace paired executions that share initial/final state satisfy low-output
equivalence. This is a scaffolding lemma only — not paired-execution NI.
-/
theorem same_execution_low_output_equivalent
    (tenantLow : String) (e : Execution) :
    LowOutputEquivalent tenantLow e e :=
  low_output_equivalent_refl tenantLow e

/--
**Honest bridge (definitional):** `TenantProjectionIsolation` on one recorded
trace is the proved observational bound. It does **not** discharge
`PairedExecutionNonInterference` for arbitrary paired executions.
-/
theorem tenant_projection_isolation_of_trace_safe
    (tenantLow tenantHigh : String) (tr : Trace) (h : TraceSafe tr) :
    TenantProjectionIsolation tenantLow tenantHigh tr :=
  traceSafe_implies_tenant_projection_isolation tenantLow tenantHigh tr h

end PFCore
