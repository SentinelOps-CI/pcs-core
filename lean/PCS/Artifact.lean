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

end PCS
