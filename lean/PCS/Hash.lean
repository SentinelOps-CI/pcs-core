/-!
# PCS canonical hashing (skeleton)

Cross-language digest rules are normative in pcs-core (`python/pcs_core/hash.py`).
This module will host Lean-side definitions aligned with shared test vectors.
-/

namespace PCS

/-- Placeholder for a SHA-256 digest string (`sha256:…`). -/
abbrev HexDigest := String

/-- Canonical JSON bytes are sorted-key UTF-8 with `signature_or_digest` stripped. -/
structure CanonicalInput where
  json : String
  deriving Repr

/-- Target invariant: `canonicalHash` is deterministic for a given artifact value. -/
def canonicalHash (_input : CanonicalInput) : HexDigest :=
  "sha256:0000000000000000000000000000000000000000000000000000000000000000"

end PCS
