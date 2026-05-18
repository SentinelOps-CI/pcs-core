/-!
# ComputationWitness trust-boundary invariants (skeleton)
-/

namespace PCS

open PCS (HexDigest)

structure ComputationWitnessV0 where
  witnessId : String
  workflowId : String
  datasetHash : HexDigest
  environmentHash : HexDigest
  runReceiptHash : HexDigest
  resultHashes : List HexDigest
  status : String
  deriving Repr

/-- Every declared result hash in a witness must correspond to a ResultArtifact digest. -/
def witnessResultHashesAdmissible (witnessResultHashes artifactHashes : List HexDigest) : Prop :=
  ∀ h ∈ witnessResultHashes, h ∈ artifactHashes

/-- ProofChecked computation releases require a CertificateChecked witness status. -/
def proofCheckedRequiresCertificateCheckedWitness (releaseStatus witnessStatus : String) : Prop :=
  releaseStatus ≠ "ProofChecked" ∨ witnessStatus = "CertificateChecked"

end PCS
