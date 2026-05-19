/-!
# PCS artifact lifecycle statuses (trust-envelope subset)
-/

namespace PCS

/-- Minimal status vocabulary for release-chain trust predicates. -/
inductive ArtifactStatus where
  | RuntimeObserved
  | CertificateChecked
  | ProofChecked
  | Rejected
  | Stale
  | Deprecated
  deriving DecidableEq, Repr

end PCS
