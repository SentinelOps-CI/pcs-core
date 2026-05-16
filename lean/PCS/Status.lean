namespace PCS

/-- Canonical PCS artifact status (v0.1). -/
inductive ArtifactStatus
  | draft
  | extracted
  | humanReviewed
  | formalized
  | proofPending
  | proofChecked
  | certificatePending
  | certificateChecked
  | runtimeObserved
  | runtimeChecked
  | rejected
  | empiricalOnly
  | deprecated
  | stale
  deriving Repr, DecidableEq

def ArtifactStatus.toJsonString : ArtifactStatus → String
  | .draft => "Draft"
  | .extracted => "Extracted"
  | .humanReviewed => "HumanReviewed"
  | .formalized => "Formalized"
  | .proofPending => "ProofPending"
  | .proofChecked => "ProofChecked"
  | .certificatePending => "CertificatePending"
  | .certificateChecked => "CertificateChecked"
  | .runtimeObserved => "RuntimeObserved"
  | .runtimeChecked => "RuntimeChecked"
  | .rejected => "Rejected"
  | .empiricalOnly => "EmpiricalOnly"
  | .deprecated => "Deprecated"
  | .stale => "Stale"

end PCS
