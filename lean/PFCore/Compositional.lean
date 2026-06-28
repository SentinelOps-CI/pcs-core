import PFCore.Contract
import PFCore.Handoff

/-!
# PF-Core compositional trust (conservative extension layer)

Conservative theorems for trace extension, handoff chaining, and sequential contract
invariants. This module does not introduce full state/transition machinery; it
composes existing kernel predicates only.
-/

namespace PFCore

/--
**Meaning:** Appending an `EventSafe` event to a `TraceSafe` trace yields `TraceSafe`.

**Trusted use:** Compositional trace-safety reasoning under controlled extension;
alias of `trace_safe_invariant_preserved_cons` with compositional naming.

**Does not imply:** Hash-chain integrity, replay validity, or contract pre/post discharge.
-/
theorem safe_extension_preserves_trace_safe (tr : Trace) (ev : Event) :
    TraceSafe tr → EventSafe ev → TraceSafe (Trace.cons tr ev) :=
  trace_safe_invariant_preserved_cons tr ev

/--
**Meaning:** The canonical trace-safe contract invariant is preserved when extending
with an `EventSafe` event.

**Trusted use:** Linking `Contract.invariant` to safe trace extension for
`require_trace_safe` discharge.

**Does not imply:** Arbitrary user-defined contract invariants hold without extra structure.
-/
theorem contract_invariant_preserved_by_safe_extension (c : Contract) (tr : Trace) (ev : Event)
    (hInv : c.invariant = traceSafeInvariant) :
    c.invariant tr → EventSafe ev → c.invariant (Trace.cons tr ev) := by
  intro htr hev
  rw [hInv] at htr ⊢
  exact trace_safe_invariant_preserved_cons tr ev htr hev

/-- Two handoffs chain when the first target equals the second source. -/
def HandoffChain (h1 h2 : Handoff) : Prop :=
  h1.toPrincipal = h2.fromPrincipal

/--
**Meaning:** Transitive handoff record from `h1` through `h2` (same tenant, subset caps).

**Trusted use:** Representing composed delegation without runtime principal mutation.
-/
def Handoff.transitive (h1 h2 : Handoff) : Handoff :=
  { fromPrincipal := h1.fromPrincipal
    toPrincipal := h2.toPrincipal
    delegatedCapabilities := h2.delegatedCapabilities }

/--
**Meaning:** Chained handoffs remain safe when the second hop delegates only capabilities
already delegated in the first hop.

**Trusted use:** Multi-hop delegation certificates where intermediate principals do not
accumulate capabilities beyond the first hop's delegation envelope.

**Does not imply:** Target principals gain capabilities from handoff without explicit
principal record updates at runtime.
-/
theorem handoff_composition_safe (h1 h2 : Handoff) :
    HandoffSafe h1 → HandoffSafe h2 → HandoffChain h1 h2 →
    CapabilitySubset h2.delegatedCapabilities h1.delegatedCapabilities →
    HandoffSafe (Handoff.transitive h1 h2) := by
  intro hs1 hs2 hchain hsub
  constructor
  · intro cap hmem
    exact hs1.left cap (hsub cap hmem)
  · simp [Handoff.transitive]
    unfold HandoffChain at hchain
    exact hs1.right.trans (congrArg Principal.tenant hchain |>.trans hs2.right)

/--
**Meaning:** Composed handoff authority does not expand beyond the original source
principal when the second hop stays within the first delegation envelope.

**Trusted use:** Chained `HandoffSafe` records; extends `handoff_does_not_expand_authority`.

**Does not imply:** Intermediate principals may exercise delegated capabilities without
separate safety checks on their actions.
-/
theorem handoff_composition_does_not_expand_authority (h1 h2 : Handoff) (cap : String) :
    HandoffSafe h1 → HandoffSafe h2 → HandoffChain h1 h2 →
    CapabilitySubset h2.delegatedCapabilities h1.delegatedCapabilities →
    cap ∈ h2.delegatedCapabilities → HasCapability h1.fromPrincipal cap := by
  intro hs1 _ _ hsub hmem
  exact handoff_does_not_expand_authority h1 cap hs1 (hsub cap hmem)

/--
**Meaning:** Sequential contract invariant on a trace splits to component invariants.

**Trusted use:** Decomposing composed contract obligations on a fixed trace prefix.

**Does not imply:** Either component alone certifies the composed system.
-/
theorem composed_contract_invariant_implies_components (c1 c2 : Contract) (tr : Trace) :
    (Contract.seq c1 c2).invariant tr → c1.invariant tr ∧ c2.invariant tr := by
  intro h
  exact h

/--
**Meaning:** When both component contract invariants hold on a trace, the sequential
contract invariant holds.

**Trusted use:** Building composed contract certificates from component invariants.

**Does not imply:** Component pre/post conditions or trace satisfaction without
`TraceSatisfiesContract` evidence.
-/
theorem composed_contract_preserves_component_invariants (c1 c2 : Contract) (tr : Trace) :
    c1.invariant tr → c2.invariant tr → (Contract.seq c1 c2).invariant tr :=
  And.intro

/-- Strong contract refines weak: strong pre implies weak pre; strong post implies weak post. -/
def ContractRefinement (cStrong cWeak : Contract) : Prop :=
  (∀ p a, cStrong.pre p a → cWeak.pre p a) ∧
  (∀ p a ev, cStrong.post p a ev → cWeak.post p a ev) ∧
  (∀ tr, cStrong.invariant tr → cWeak.invariant tr)

/--
**Meaning:** Satisfying a strong contract on a trace implies satisfaction of any refined weak contract.

**Trusted use:** Contract refinement certificates without re-discharge on sub-traces.

**Does not imply:** Component contracts refine each other without explicit `ContractRefinement` evidence.
-/
theorem contract_refinement_preserves_trace_safe (cStrong cWeak : Contract) (tr : Trace) :
    TraceSatisfiesContract cStrong tr → ContractRefinement cStrong cWeak →
    TraceSatisfiesContract cWeak tr := by
  intro hStrong hRef
  induction tr with
  | empty => trivial
  | cons tr' ev ih =>
    unfold TraceSatisfiesContract at hStrong ⊢
    rcases hStrong with ⟨hTrStrong, hEvStrong, hInvStrong⟩
    rcases hRef with ⟨hPre, hPost, hInv⟩
    rcases ih hTrStrong with hTrWeak
    refine ⟨hTrWeak, ?_, hInv (Trace.cons tr' ev) hInvStrong⟩
    · unfold SatisfiesContract at hEvStrong ⊢
      rcases hEvStrong with ⟨hPreStrong, hPostStrong⟩
      refine ⟨hPre ev.principal ev.action hPreStrong, ?_⟩
      cases hPostStrong with
      | inl hdeny => exact Or.inl hdeny
      | inr hpost => exact Or.inr (hPost ev.principal ev.action ev hpost)

/--
**Meaning:** Chained handoffs stay within the original source authority for any hop length.

**Trusted use:** Global multi-hop delegation without authority expansion beyond first source.

**Does not imply:** Intermediate principals may act without event safety or tenant checks.
-/
theorem handoff_composition_global (h1 h2 : Handoff) (cap : String) :
    HandoffSafe h1 → HandoffSafe h2 → HandoffChain h1 h2 →
    CapabilitySubset h2.delegatedCapabilities h1.delegatedCapabilities →
    cap ∈ h2.delegatedCapabilities → HasCapability h1.fromPrincipal cap := by
  intro hs1 hs2 hchain hsub hmem
  exact handoff_composition_does_not_expand_authority h1 h2 cap hs1 hs2 hchain hsub hmem

/--
**Meaning:** Three-hop handoff chains remain bounded by the first source principal.

**Trusted use:** Stronger global handoff composition beyond conservative two-hop chaining.

**Does not imply:** Runtime handoff ordering or replay-validated delegation sequences.
-/
theorem handoff_composition_global_three (h1 h2 h3 : Handoff) (cap : String) :
    HandoffSafe h1 → HandoffSafe h2 → HandoffSafe h3 →
    HandoffChain h1 h2 → HandoffChain h2 h3 →
    CapabilitySubset h2.delegatedCapabilities h1.delegatedCapabilities →
    CapabilitySubset h3.delegatedCapabilities h2.delegatedCapabilities →
    cap ∈ h3.delegatedCapabilities → HasCapability h1.fromPrincipal cap := by
  intro hs1 hs2 hs3 h12 h23 hsub12 hsub23 hmem
  have hmem2 : cap ∈ h2.delegatedCapabilities := hsub23 cap hmem
  exact handoff_composition_global h1 h2 cap hs1 hs2 h12 hsub12 hmem2

/--
**Meaning:** When both components use the trace-safe invariant, safe extension preserves
the sequential contract invariant.

**Trusted use:** Compositional `Contract.seq` with `require_trace_safe` on each component.

**Does not imply:** Custom invariants for either component are preserved without
matching `traceSafeInvariant` structure.
-/
theorem composed_trace_safe_invariant_preserved_by_safe_extension
    (c1 c2 : Contract) (tr : Trace) (ev : Event)
    (hInv1 : c1.invariant = traceSafeInvariant) (hInv2 : c2.invariant = traceSafeInvariant) :
    (Contract.seq c1 c2).invariant tr → EventSafe ev →
    (Contract.seq c1 c2).invariant (Trace.cons tr ev) := by
  intro hInv hev
  rcases composed_contract_invariant_implies_components c1 c2 tr hInv with ⟨h1, h2⟩
  rw [hInv1] at h1
  rw [hInv2] at h2
  exact composed_contract_preserves_component_invariants c1 c2 (Trace.cons tr ev)
    (by rw [hInv1]; exact trace_safe_invariant_preserved_cons tr ev h1 hev)
    (by rw [hInv2]; exact trace_safe_invariant_preserved_cons tr ev h2 hev)

end PFCore
