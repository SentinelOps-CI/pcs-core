/-!
# Tool-use trust-boundary (trace/certificate hash alignment only)
-/

import PCS.Hash

namespace PCS

structure ToolUseCertificate where
  certificateId : String
  traceHash : Hash
  policyHash : Hash
  status : String
  deriving Repr

structure ToolUseTrace where
  traceId : String
  traceHash : Hash
  policyHash : Hash
  deriving Repr

def toolTraceHashMatchesCertificate (trace : ToolUseTrace) (cert : ToolUseCertificate) : Prop :=
  cert.traceHash = trace.traceHash ∧ cert.policyHash = trace.policyHash

end PCS
