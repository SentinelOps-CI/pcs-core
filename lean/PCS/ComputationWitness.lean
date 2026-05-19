/-!
# ComputationWitness trust-boundary (structural hash alignment only)
-/

import PCS.Hash

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

/-- ProofChecked computation releases require a CertificateChecked witness status string. -/
def proofCheckedRequiresCertificateCheckedWitness (releaseStatus witnessStatus : String) : Prop :=
  releaseStatus ≠ "ProofChecked" ∨ witnessStatus = "CertificateChecked"

end PCS
