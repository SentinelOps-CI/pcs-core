/-!
# Cross-artifact hash binding (skeleton)
-/

namespace PCS

open PCS (HexDigest)

/-- Signed bundle hash must equal the certified bundle hash verified by PF. -/
def signedBundleBindsCertifiedHash (signedHash certifiedHash : HexDigest) : Prop :=
  signedHash = certifiedHash

/-- Witness binds dataset receipt aggregate hash. -/
def witnessBindsDatasetHash (witnessDatasetHash receiptAggregateHash : HexDigest) : Prop :=
  witnessDatasetHash = receiptAggregateHash

end PCS
