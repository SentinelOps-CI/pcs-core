/-!
# PCS canonical hashes (abstracted from JSON digests)
-/

namespace PCS

structure Hash where
  value : String
  deriving DecidableEq, Repr

def Hash.ofString (value : String) : Hash := ⟨value⟩

instance : BEq Hash where
  beq a b := a.value == b.value

theorem hash_beq_iff_eq (a b : Hash) : (a == b) = true ↔ a = b := by
  cases a with | mk av =>
  cases b with | mk bv =>
  simp [BEq.beq, decide_eq_true_iff, beq_iff_eq, Hash.mk.injEq]

end PCS
