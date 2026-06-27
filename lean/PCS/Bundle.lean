/-!
# PCS bundle verification (Provability Fabric export)
-/

import PCS.Hash
import PCS.Status

namespace PCS

structure VerificationResult where
  status : ArtifactStatus
  verifiedInputBundleHash : Hash
  releaseBlockingChecksPassed : Bool
  deriving DecidableEq, Repr

end PCS
