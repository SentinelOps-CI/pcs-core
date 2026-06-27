import PCS.Hash
import PCS.Status

/-!
# PCS bundle verification (Provability Fabric export)
-/

namespace PCS

structure VerificationResult where
  status : ArtifactStatus
  verifiedInputBundleHash : Hash
  releaseBlockingChecksPassed : Bool
  deriving DecidableEq, Repr

end PCS
