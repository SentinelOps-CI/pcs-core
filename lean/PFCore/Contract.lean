import PFCore.Trace

/-!
# PF-Core contracts on events and traces
-/

namespace PFCore

/-- Named contract with pre/post conditions and trace invariant. -/
structure Contract where
  name : String
  pre : Principal → Action → Prop
  post : Principal → Action → Event → Prop
  invariant : Trace → Prop

/-- Canonical trace-safety invariant used by JSON `invariant.require_trace_safe`. -/
def traceSafeInvariant : Trace → Prop := TraceSafe

/-- Contract whose invariant is trace safety (matches runtime `require_trace_safe`). -/
def traceSafeContract : Contract :=
  { name := "trace-safe"
    pre := fun _ _ => True
    post := fun _ _ _ => True
    invariant := traceSafeInvariant }

/--
**Meaning:** Appending a safe event preserves the canonical `TraceSafe` invariant.

**Trusted use:** Contract invariant preservation for `require_trace_safe` JSON fields.

**Does not imply:** Arbitrary user contract invariants are preserved without extra structure.
-/
theorem trace_safe_invariant_preserved_cons (tr : Trace) (ev : Event) :
    TraceSafe tr → EventSafe ev → TraceSafe (Trace.cons tr ev) := by
  intro htr hev
  exact (traceSafe_cons tr ev).mpr ⟨htr, hev⟩

/--
**Meaning:** The packaged trace-safe contract invariant is preserved under `Trace.cons`.

**Trusted use:** Mapping JSON `invariant.require_trace_safe` to Lean preservation lemmas.

**Does not imply:** Custom contract invariants hold without additional proof obligations.
-/
theorem invariant_preserved_cons (tr : Trace) (ev : Event) :
    traceSafeContract.invariant tr → EventSafe ev →
    traceSafeContract.invariant (Trace.cons tr ev) :=
  trace_safe_invariant_preserved_cons tr ev

/-- Single event satisfies contract pre and post (when allowed). -/
def SatisfiesContract (c : Contract) (ev : Event) : Prop :=
  c.pre ev.principal ev.action ∧
  (ev.decision = Decision.deny ∨ c.post ev.principal ev.action ev)

def TraceSatisfiesContract (c : Contract) : Trace → Prop
  | Trace.empty => True
  | Trace.cons tr ev =>
    TraceSatisfiesContract c tr ∧
    SatisfiesContract c ev ∧
    c.invariant (Trace.cons tr ev)

/-- Sequential composition of two contracts (both must hold). -/
def Contract.seq (c1 c2 : Contract) : Contract :=
  { name := c1.name ++ ";" ++ c2.name
    pre := fun p a => c1.pre p a ∧ c2.pre p a
    post := fun p a ev => c1.post p a ev ∧ c2.post p a ev
    invariant := fun tr => c1.invariant tr ∧ c2.invariant tr }

/--
**Meaning:** Sequential contract satisfaction on an event splits to component contracts.

**Trusted use:** Compositional contract reasoning in multi-contract traces.

**Does not imply:** Sequential composition preserves invariants without both sides holding.
-/
theorem seq_contract_satisfaction_left (c1 c2 : Contract) (ev : Event) :
    SatisfiesContract (Contract.seq c1 c2) ev ↔
      SatisfiesContract c1 ev ∧ SatisfiesContract c2 ev := by
  simp only [SatisfiesContract, Contract.seq]
  constructor
  · rintro ⟨⟨hp1, hp2⟩, hpost⟩
    constructor
    · exact ⟨hp1, Or.elim hpost Or.inl (fun h => Or.inr h.1)⟩
    · exact ⟨hp2, Or.elim hpost Or.inl (fun h => Or.inr h.2)⟩
  · rintro ⟨⟨hp1, hpost1⟩, ⟨hp2, hpost2⟩⟩
    refine ⟨⟨hp1, hp2⟩, ?_⟩
    rcases hpost1 with (deny1 | post1) <;> rcases hpost2 with (deny2 | post2)
    · exact Or.inl deny1
    · exact Or.inl deny1
    · exact Or.inl deny2
    · exact Or.inr ⟨post1, post2⟩

/--
**Meaning:** Sequential trace-level contract satisfaction splits to component traces.

**Trusted use:** Trace-wide compositional contract discharge in Lean codegen.

**Does not imply:** Either component contract alone certifies the composed system.
-/
theorem seq_contract_satisfaction_right (c1 c2 : Contract) (tr : Trace) :
    TraceSatisfiesContract (Contract.seq c1 c2) tr ↔
      TraceSatisfiesContract c1 tr ∧ TraceSatisfiesContract c2 tr := by
  induction tr with
  | empty => simp [TraceSatisfiesContract, Contract.seq]
  | cons tr ev ih =>
    constructor
    · intro h
      unfold TraceSatisfiesContract Contract.seq at h
      rcases h with ⟨hTr, hEv, hInv1, hInv2⟩
      rcases ih.mp hTr with ⟨hTr1, hTr2⟩
      rcases (seq_contract_satisfaction_left c1 c2 ev).mp hEv with ⟨hEv1, hEv2⟩
      exact ⟨⟨hTr1, hEv1, hInv1⟩, ⟨hTr2, hEv2, hInv2⟩⟩
    · intro h
      rcases h with ⟨⟨hTr1, hEv1, hInv1⟩, ⟨hTr2, hEv2, hInv2⟩⟩
      unfold TraceSatisfiesContract Contract.seq
      refine ⟨ih.mpr ⟨hTr1, hTr2⟩, ?_, hInv1, hInv2⟩
      exact (seq_contract_satisfaction_left c1 c2 ev).mpr ⟨hEv1, hEv2⟩

end PFCore
