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
  cert.traceHash = trace.traceHash ? cert.policyHash = trace.policyHash

def toolTraceHashMatchesCertificateD (trace : ToolUseTrace) (cert : ToolUseCertificate) : Bool :=
  decide (cert.traceHash = trace.traceHash && cert.policyHash = trace.policyHash)

theorem tool_trace_hash_matches_certificate (trace : ToolUseTrace) (cert : ToolUseCertificate) :
    toolTraceHashMatchesCertificateD trace cert = true ?
      toolTraceHashMatchesCertificate trace cert := by
  simp [toolTraceHashMatchesCertificateD, toolTraceHashMatchesCertificate, decide_eq_true_iff]

end PCS
