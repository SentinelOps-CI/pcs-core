/-!
# Certificate references (trust-boundary skeleton)
-/

namespace PCS

open PCS (HexDigest)

structure CertificateRef where
  certificateId : String
  traceHash : HexDigest
  deriving Repr

/-- Invariant: every certificate reference resolves to an existing certificate id. -/
def certificateRefResolves (refs : List CertificateRef) (knownIds : List String) : Prop :=
  ∀ ref ∈ refs, ref.certificateId ∈ knownIds

/-- Invariant: checked certificates cite the runtime trace hash. -/
def checkedCertificateMatchesTrace (ref : CertificateRef) (runtimeTraceHash : HexDigest) : Prop :=
  ref.traceHash = runtimeTraceHash

end PCS
