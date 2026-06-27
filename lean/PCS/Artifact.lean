/-!
# PCS artifact references
-/

import PCS.Hash

namespace PCS

structure ArtifactRef where
  artifactId : String
  artifactType : String
  hash : Hash
  deriving DecidableEq, Repr

structure SourcePosition where
  line : Nat
  column : Nat
  deriving Repr

structure SourceSpanV0 where
  sourceSpanId : String
  schemaVersion : String := "v0"
  sourceType : String
  sourceUri : String
  start : SourcePosition
  endPos : SourcePosition
  hash : String
  description : String
  deriving Repr

structure AssumptionV0 where
  assumptionId : String
  text : String
  kind : String
  status : String
  sourceSpanRefs : List String
  deriving Repr

structure AssumptionSetV0 where
  assumptionSetId : String
  schemaVersion : String := "v0"
  createdAt : String
  producer : String
  producerVersion : String
  sourceRepo : String
  sourceCommit : String
  assumptions : List AssumptionV0
  humanReviewStatus : String
  status : String
  signatureOrDigest : String
  deriving Repr

end PCS
