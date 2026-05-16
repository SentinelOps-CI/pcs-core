import PCS.Artifact
import PCS.Claim
import PCS.RuntimeReceipt
import PCS.TraceCertificate

namespace PCS

structure EvidenceBundleV0 where
  bundleId : String
  schemaVersion : String := "v0"
  claimRefs : List String
  assumptionSetRefs : List String
  runtimeReceiptRefs : List String
  certificateRefs : List String
  createdAt : String
  producer : String
  producerVersion : String
  sourceRepo : String
  sourceCommit : String
  signatureOrDigest : String
  deriving Repr

structure ScienceClaimBundleV0 where
  bundleId : String
  schemaVersion : String := "v0"
  claimArtifact : ClaimArtifactV0
  assumptionSet : AssumptionSetV0
  runtimeReceipts : List RuntimeReceiptV0
  certificates : List TraceCertificateV0
  evidenceBundle : EvidenceBundleV0
  createdAt : String
  producer : String
  producerVersion : String
  sourceRepo : String
  sourceCommit : String
  signatureOrDigest : String
  deriving Repr

end PCS
