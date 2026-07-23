/-!
# PF-Core digest values (abstracted from JSON digests)
-/

namespace PFCore

/-- Opaque digest string used for observation and attestation bindings. -/
structure Hash where
  value : String
deriving Repr, DecidableEq

def Hash.ofString (value : String) : Hash := ⟨value⟩

instance : BEq Hash where
  beq a b := a.value == b.value

theorem hash_beq_iff_eq (a b : Hash) : (a == b) = true ↔ a = b := by
  cases a with | mk av =>
  cases b with | mk bv =>
  simp [BEq.beq, decide_eq_true_iff, beq_iff_eq, Hash.mk.injEq]

end PFCore
