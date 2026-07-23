/-!
# PF-Core effect kinds
-/

namespace PFCore

/-- Effect kinds for tool actions (closed enum plus custom labels). -/
inductive Effect where
  | read | write | network | externalMessage | codeExecution | stateChange
  | custom : String → Effect
deriving Repr, DecidableEq

end PFCore
