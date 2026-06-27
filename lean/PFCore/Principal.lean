import PFCore.Basic

/-!
# PF-Core principals
-/

namespace PFCore

/-- Agent or service identity with tenant scope and granted capabilities. -/
structure Principal where
  id : String
  tenant : String
  roles : List String
  capabilities : List String
deriving Repr, DecidableEq

end PFCore
