import PCS.Artifact

namespace PCS

structure ClaimArtifactV0 where
  artifactId : String
  artifactType : String := "ClaimArtifact.v0"
  schemaVersion : String := "v0"
  claimText : String
  claimKind : String
  status : String
  assumptionSetRef : String
  sourceSpanRefs : List String
  formalStatement : String
  certificateRefs : List String
  runtimeReceiptRefs : List String
  createdAt : String
  producer : String
  producerVersion : String
  sourceRepo : String
  sourceCommit : String
  signatureOrDigest : String
  deriving Repr

end PCS
