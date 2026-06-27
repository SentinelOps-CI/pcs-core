/-!
# PF-Core trust kernel — basic definitions

Root namespace for the PF-Core action-trace kernel. This package models
capability-bounded action safety on traces; it does not encode PCS
release-envelope or scientific-domain claims.
-/

namespace PFCore

/-- PF-Core kernel version string (protocol metadata only). -/
def pfCoreKernelVersion : String := "0.1.0"

end PFCore
