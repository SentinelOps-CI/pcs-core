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

end PCS
