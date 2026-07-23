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

/-- Witness result hashes must be drawn from an independently declared artifact digest set. -/
def witnessResultHashesAdmissible (witness : ComputationWitness) (artifactHashes : List Hash) : Prop :=
  ∀ h ∈ witness.resultHashes, h ∈ artifactHashes

/-- Deprecated circular helper retained only for legacy catalogs; do not use in generated proofs. -/
def witnessDeclaredArtifactHashes (witness : ComputationWitness) : List Hash :=
  witness.resultHashes

theorem witness_result_hashes_admissible
    (witness : ComputationWitness) (artifactHashes : List Hash)
    (h : witnessResultHashesAdmissible witness artifactHashes)
    (resultHash : Hash) (hmem : resultHash ∈ witness.resultHashes) :
    resultHash ∈ artifactHashes :=
  h resultHash hmem

/-- ProofChecked computation releases require a CertificateChecked witness status string. -/
def proofCheckedRequiresCertificateCheckedWitness (releaseStatus witnessStatus : String) : Prop :=
  releaseStatus = "ProofChecked" → witnessStatus = "CertificateChecked"

/-- Decidable check: a concrete result artifact digest appears in witness result_hashes. -/
def witnessResultHashListedD (resultHashes : List Hash) (artifactHash : Hash) : Bool :=
  resultHashes.any fun h => h == artifactHash

theorem witness_result_hash_listedD_sound (resultHashes : List Hash) (artifactHash : Hash) :
    witnessResultHashListedD resultHashes artifactHash = true ↔ artifactHash ∈ resultHashes := by
  simp [witnessResultHashListedD, List.any_eq_true, decide_eq_true_iff, hash_beq_iff_eq]

/-- Decidable check: every witness result hash appears in the declared artifact digest set. -/
def witnessResultHashesAdmissibleD (witnessResultHashes artifactHashes : List Hash) : Bool :=
  witnessResultHashes.all fun witnessHash =>
    artifactHashes.any fun artifactHash => decide (witnessHash == artifactHash)

theorem witnessResultHashesAdmissibleD_sound (witnessResultHashes artifactHashes : List Hash) :
    witnessResultHashesAdmissibleD witnessResultHashes artifactHashes = true ↔
      ∀ h ∈ witnessResultHashes, h ∈ artifactHashes := by
  simp [witnessResultHashesAdmissibleD, List.all_eq_true, List.any_eq_true, decide_eq_true_iff,
    hash_beq_iff_eq]

end PCS
