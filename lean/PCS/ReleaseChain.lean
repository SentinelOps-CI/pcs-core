/-!
# Release-chain trust invariants (skeleton)
-/

namespace PCS

open PCS (HexDigest)

structure ValidationCheck where
  checkId : String
  status : String
  registryRefs : List String
  deriving Repr

/-- Invariant: ProofChecked releases have no failed release-blocking checks. -/
def proofCheckedHasNoFailedBlocking (checks : List ValidationCheck) : Prop :=
  ∀ check ∈ checks, check.status ≠ "failed"

/-- Invariant: signed bundle hash equals verified input bundle hash (PF export). -/
def signedBundleMatchesVerifiedInput (signedHash verifiedHash : HexDigest) : Prop :=
  signedHash = verifiedHash

/-- Invariant: ProofChecked computation release requires CertificateChecked witness. -/
def proofCheckedComputationRequiresCheckedWitness (releaseStatus witnessStatus : String) : Prop :=
  releaseStatus ≠ "ProofChecked" ∨ witnessStatus = "CertificateChecked"

/-- Invariant: signed computation bundle binds PF-verified certified bundle hash. -/
def signedComputationBundleMatchesCertified (signedHash certifiedHash : HexDigest) : Prop :=
  signedHash = certifiedHash

end PCS
