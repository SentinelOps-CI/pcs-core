import PFCore.Contract
import PFCore.Handoff

/-!
# PF-Core operational state and transition model

Rich state tracks tenant, active principal, declared resource frame, and capability
frame. Operational `stepState` applies allowed events (merging action reads/writes
into the resource frame) and leaves state unchanged on deny.
-/

namespace PFCore

/-- Operational runtime snapshot with resource and capability frames. -/
structure State where
  tenant : String
  activePrincipal : Principal
  resourceFrame : List Resource
  capabilityFrame : List String
deriving Repr, DecidableEq

/-- One operational step from pre-state through an event to post-state. -/
structure Transition where
  pre : State
  post : State
  event : Event
deriving Repr

/-- Insert resource `r` into frame when absent (structural equality). -/
def insertResource (frame : List Resource) (r : Resource) : List Resource :=
  if r ∈ frame then frame else r :: frame

/-- Expand frame with all read/write resources declared on action `a`. -/
def expandResourceFrame (frame : List Resource) (a : Action) : List Resource :=
  List.foldl insertResource frame (a.reads ++ a.writes)

/-- All resources in frame belong to tenant `t`. -/
def frameTenantScoped (t : String) (frame : List Resource) : Prop :=
  ∀ r ∈ frame, r.tenant = t

/-- Capability frame is a subset of the active principal capability list. -/
def capabilityFrameSubset (s : State) : Prop :=
  CapabilitySubset s.capabilityFrame s.activePrincipal.capabilities

/-- Frame well-formedness: tenant alignment and capability subset. -/
def FrameValid (s : State) : Prop :=
  s.tenant = s.activePrincipal.tenant ∧
  frameTenantScoped s.tenant s.resourceFrame ∧
  capabilityFrameSubset s

def frameValidD (s : State) : Bool :=
  decide (s.tenant = s.activePrincipal.tenant) &&
    s.resourceFrame.all (fun r => decide (r.tenant = s.tenant)) &&
    capabilitySubsetD s.capabilityFrame s.activePrincipal.capabilities

/--
**Meaning:** Frame validity decider reflects `FrameValid`.

**Trusted use:** Runtime alignment for operational state certificates.

**Does not imply:** Action allowance, trace safety, or hash-chain integrity.
-/
theorem frameValidD_sound (s : State) :
    frameValidD s = true ↔ FrameValid s := by
  unfold frameValidD FrameValid frameTenantScoped capabilityFrameSubset
  simp [capabilitySubsetD_sound, List.all_eq_true, decide_eq_true_iff, and_left_comm, and_assoc]

private theorem insertResource_mem (frame : List Resource) (r res : Resource) :
    res ∈ insertResource frame r ↔ res ∈ frame ∨ res = r := by
  by_cases hin : r ∈ frame
  · simp only [insertResource, hin]
    apply Iff.intro
    · intro h; exact Or.inl h
    · intro h; rcases h with hfr | heq; exact hfr; exact heq ▸ hin
  · simp [insertResource, hin, List.mem_cons, eq_comm, or_comm]

private theorem insertResource_preserves_tenant (t : String) (frame : List Resource) (r : Resource)
    (hframe : frameTenantScoped t frame) (hr : r.tenant = t) :
    frameTenantScoped t (insertResource frame r) := by
  intro res hres
  rw [insertResource_mem] at hres
  cases hres with
  | inl hfr => exact hframe res hfr
  | inr heq => exact heq.symm ▸ hr

private theorem frameTenantScoped_foldl_insert (t : String) (frame rs : List Resource)
    (hframe : frameTenantScoped t frame)
    (hresources : ∀ r ∈ rs, r.tenant = t) :
    frameTenantScoped t (List.foldl insertResource frame rs) := by
  induction rs generalizing frame with
  | nil => simpa using hframe
  | cons head tail ih =>
    have hhead : head.tenant = t := hresources head (List.mem_cons_self head tail)
    have hrest : ∀ r ∈ tail, r.tenant = t := by
      intro r hr
      exact hresources r (List.mem_cons_of_mem head hr)
    exact ih (insertResource frame head) (insertResource_preserves_tenant t frame head hframe hhead) hrest

private theorem resources_tenant (p : Principal) (a : Action) (r : Resource)
    (hwithin : ActionWithinTenant p a) :
    r ∈ a.reads → r.tenant = p.tenant := fun hr => (hwithin.left r hr).symm

private theorem resources_tenant_write (p : Principal) (a : Action) (r : Resource)
    (hwithin : ActionWithinTenant p a) :
    r ∈ a.writes → r.tenant = p.tenant := fun hr => (hwithin.right r hr).symm

private theorem expandResourceFrame_tenant (frame : List Resource) (a : Action) (p : Principal)
    (htFrame : frameTenantScoped p.tenant frame) (hwithin : ActionWithinTenant p a) :
    frameTenantScoped p.tenant (expandResourceFrame frame a) := by
  unfold expandResourceFrame
  refine frameTenantScoped_foldl_insert p.tenant frame (a.reads ++ a.writes) htFrame ?_
  intro r hr
  simp [List.mem_append] at hr
  cases hr with
  | inl hread => exact resources_tenant p a r hwithin hread
  | inr hwrite => exact resources_tenant_write p a r hwithin hwrite

/-- Operational step: allow updates principal and expands frame; deny is identity. -/
def stepState (s : State) (ev : Event) : Option State :=
  match ev.decision with
  | Decision.deny => some s
  | Decision.allow =>
    if actionAllowedD ev.principal ev.action && (s.tenant == ev.principal.tenant) then
      some
        { tenant := ev.principal.tenant
          activePrincipal := ev.principal
          resourceFrame := expandResourceFrame s.resourceFrame ev.action
          capabilityFrame := ev.principal.capabilities }
    else none

/-- Post-state `s'` applies event `ev` from pre-state `s` when `stepState` succeeds. -/
def Applies (ev : Event) (s s' : State) : Prop :=
  stepState s ev = some s'

/-- On allow, expanded frame covers action footprint; on deny, state is unchanged. -/
def FramePreserved (ev : Event) (s s' : State) : Prop :=
  Applies ev s s' →
    (ev.decision = Decision.deny → s = s') ∧
    (ev.decision = Decision.allow →
      s'.resourceFrame = expandResourceFrame s.resourceFrame ev.action ∧
      s'.activePrincipal = ev.principal ∧
      s'.tenant = ev.principal.tenant)

/-- Safe trace extension linkage: prefix safe and new event safe. -/
def TraceExtendsSafely (tr : Trace) (ev : Event) : Prop :=
  TraceSafe tr ∧ EventSafe ev

def traceExtendsSafelyD (tr : Trace) (ev : Event) : Bool :=
  traceSafeD tr && eventSafeD ev

/--
**Meaning:** Safe-extension decider reflects `TraceExtendsSafely`.

**Trusted use:** Bridging operational steps to `TraceSafe` extension lemmas.

**Does not imply:** Frame validity, contract discharge, or replay integrity.
-/
theorem traceExtendsSafelyD_sound (tr : Trace) (ev : Event) :
    traceExtendsSafelyD tr ev = true ↔ TraceExtendsSafely tr ev := by
  simp [traceExtendsSafelyD, TraceExtendsSafely, traceSafeD_sound, eventSafeD_sound,
    Bool.and_eq_true, and_left_comm]

/--
**Meaning:** Allowed operational steps preserve frame invariants and expand declared footprint.

**Trusted use:** State-level certificates for resource/capability frame discipline.

**Does not imply:** Trace safety without separate `EventSafe` evidence or cross-event frame monotonicity.
-/
theorem stepState_frame_preserved (s s' : State) (ev : Event) (hApply : Applies ev s s') :
    FrameValid s → FrameValid s' := by
  intro hValid
  unfold Applies at hApply
  cases hdec : ev.decision with
  | deny =>
    simp [stepState, hdec] at hApply
    cases hApply
    exact hValid
  | allow =>
    by_cases hallowed : actionAllowedD ev.principal ev.action = true
    · by_cases ht : (s.tenant == ev.principal.tenant) = true
      · rcases hValid with ⟨htenant, hframe, _⟩
        have hstate :
            s' =
              { tenant := ev.principal.tenant
                activePrincipal := ev.principal
                resourceFrame := expandResourceFrame s.resourceFrame ev.action
                capabilityFrame := ev.principal.capabilities } := by
          simp [stepState, hdec, hallowed, ht, beq_iff_eq] at hApply
          exact hApply.symm
        subst hstate
        have hAct : ActionAllowed ev.principal ev.action :=
          (actionAllowedD_sound ev.principal ev.action).mp hallowed
        have hwithin : ActionWithinTenant ev.principal ev.action := hAct.right.left
        have htenant_eq : s.tenant = ev.principal.tenant := by
          simpa [htenant] using beq_iff_eq.mp ht
        refine ⟨rfl, expandResourceFrame_tenant s.resourceFrame ev.action ev.principal (htenant_eq ▸ hframe) hwithin, ?_⟩
        intro cap hmem
        exact hmem
      · simp [stepState, hdec, hallowed, ht] at hApply
    · simp [stepState, hdec, hallowed] at hApply

/--
**Meaning:** Successful `stepState` on an allowed safe event yields `TraceExtendsSafely`.

**Trusted use:** Linking operational semantics to compositional trace extension.

**Does not imply:** Full trace membership or contract satisfaction.
-/
theorem traceExtendsSafely_of_step (tr : Trace) (s s' : State) (ev : Event)
    (hTrace : TraceSafe tr) (hEvSafe : EventSafe ev) (_hApply : Applies ev s s') :
    TraceExtendsSafely tr ev :=
  ⟨hTrace, hEvSafe⟩

/--
**Meaning:** Safe trace extension with frame preservation yields `TraceSafe` on `Trace.cons`.

**Trusted use:** Strong compositional extension combining frames and trace safety.

**Does not imply:** Operational replay, hash chains, or automatic contract discharge.
-/
theorem safe_extension_preserves_trace_safe_strong (tr : Trace) (ev : Event)
    (s s' : State) (hExt : TraceExtendsSafely tr ev) (_hApply : Applies ev s s')
    (_hFrame : FrameValid s → FrameValid s') :
    TraceSafe (Trace.cons tr ev) := by
  rcases hExt with ⟨hTr, hEv⟩
  exact trace_safe_invariant_preserved_cons tr ev hTr hEv

/--
**Meaning:** `Applies` with valid pre-frame implies post-frame validity after `stepState`.

**Trusted use:** Corollary packaging `stepState_frame_preserved` for certificates.

**Does not imply:** Trace-wide frame validity without inductive state initialization.
-/
theorem applies_preserves_frame_valid (ev : Event) (s s' : State)
    (hApply : Applies ev s s') (hValid : FrameValid s) : FrameValid s' :=
  stepState_frame_preserved s s' ev hApply hValid

end PFCore
