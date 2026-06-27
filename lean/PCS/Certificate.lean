import PCS.Hash
import PCS.Status

/-!
# PCS certificate and runtime receipt (trust envelope)
-/

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
