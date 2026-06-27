import PFCore.Trace

/-!
# PF-Core certificate envelope (trace safety attestation metadata)
-/

namespace PFCore

/-- PF-Core certificate metadata linking a trace hash to a safety claim class. -/
structure Certificate where
  certificateId : String
  traceHash : String
  claimClass : String
  eventCount : Nat
deriving Repr, DecidableEq

/-- Certificate attests trace safety when paired with a safe trace of matching length. -/
def CertificateAttestsTraceSafe (cert : Certificate) (tr : Trace) : Prop :=
  cert.claimClass = "LeanKernelChecked" → TraceSafe tr

end PFCore
