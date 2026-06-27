import PCS.Hash

/-!
# ComputationWitness trust-boundary (structural hash alignment only)
-/

namespace PCS

structure ComputationWitness where
  witnessId : String
  datasetHash : Hash
  environmentHash : Hash
  runReceiptHash : Hash
  resultHashes : List Hash
  status : String
  deriving Repr

/-- Witness result hashes must be drawn from the declared result artifact digest set. -/
def witnessResultHashesAdmissible (witness : ComputationWitness) (artifactHashes : List Hash) : Prop :=
  ∀ h ∈ witness.resultHashes, h ∈ artifactHashes

theorem witness_result_hashes_admissible
    (witness : ComputationWitness) (artifactHashes : List Hash)
    (h : witnessResultHashesAdmissible witness artifactHashes)
    (resultHash : Hash) (hmem : resultHash ∈ witness.resultHashes) :
    resultHash ∈ artifactHashes :=
  h resultHash hmem

/-- ProofChecked computation releases require a CertificateChecked witness status string. -/
def proofCheckedRequiresCertificateCheckedWitness (releaseStatus witnessStatus : String) : Prop :=
  releaseStatus ≠ "ProofChecked" ∨ witnessStatus = "CertificateChecked"

end PCS
