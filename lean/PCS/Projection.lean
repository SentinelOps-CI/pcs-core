import PCS.Bundle
import PCS.Certificate
import PCS.Hash
import PCS.ReleaseChain

/-!
# PCS release-envelope projection binding

`EnvelopeProjectionMeta` carries workflow/release identity and the PCS projection
digest. `ReleaseEnvelope` extends that meta with concrete release-chain values so
`EnvelopeLeanChecked` witnesses cannot treat the projection as metadata-only.
-/

namespace PCS

/-- Workflow/release identity bound to a PCS projection digest. -/
structure EnvelopeProjectionMeta where
  workflowId : String
  releaseId : String
  projectionDigest : Hash
  deriving DecidableEq, Repr

/-- Projection digest and identities must be present to participate in a witness. -/
def EnvelopeProjectionBound (meta : EnvelopeProjectionMeta) : Prop :=
  meta.projectionDigest.value ≠ "" ∧
  meta.workflowId ≠ "" ∧
  meta.releaseId ≠ ""

/-- Concrete PCS release envelope: projection meta + release-chain values. -/
structure ReleaseEnvelope where
  workflowId : String
  releaseId : String
  projectionDigest : Hash
  certificate : Certificate
  runtimeReceipt : RuntimeReceipt
  verification : VerificationResult
  certifiedBundleHash : Hash
  signedInputHash : Hash
  deriving DecidableEq, Repr

def ReleaseEnvelope.toProjectionMeta (env : ReleaseEnvelope) : EnvelopeProjectionMeta :=
  {
    workflowId := env.workflowId
    releaseId := env.releaseId
    projectionDigest := env.projectionDigest
  }

/-- Release-admissibility over a fully projected envelope (B2). -/
def EnvelopeReleaseAdmissible (env : ReleaseEnvelope) : Prop :=
  EnvelopeProjectionBound env.toProjectionMeta ∧
  ReleaseChainAdmissible
    env.certificate
    env.runtimeReceipt
    env.verification
    env.certifiedBundleHash
    env.signedInputHash

end PCS
