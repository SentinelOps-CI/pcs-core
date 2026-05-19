/-!
# PCS certificate and runtime receipt (trust envelope)
-/

import PCS.Hash
import PCS.Status

namespace PCS

structure Certificate where
  certificateId : String
  traceHash : Hash
  status : ArtifactStatus
  deriving DecidableEq, Repr

structure RuntimeReceipt where
  traceHash : Hash
  status : ArtifactStatus
  deriving DecidableEq, Repr

end PCS
