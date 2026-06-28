import PFCore.Resource

/-!
# PF-Core resource URI patterns (runtime parity subset)

Finite pattern language aligned with Python `resource_matches_pattern` / `fnmatch`
for PF-Core capability `resource_pattern` values (`*`, `/data/*`, `mailto:*`, etc.).

Pattern matching is discharged at **runtime** during lean-check resource-scope validation;
the Lean kernel records `contract_semantics_checked.runtime` for `resource_pattern_scope`
but does not prove pattern discharge inside `EventSafe` / `TraceSafe`.
-/

namespace PFCore

/-- Capability resource scope patterns (closed catalog + glob strings). -/
inductive ResourcePattern where
  | any : ResourcePattern
  | glob (pattern : String) : ResourcePattern
deriving Repr, DecidableEq

def ResourcePattern.ofString (s : String) : ResourcePattern :=
  if s = "*" then ResourcePattern.any else ResourcePattern.glob s

/-- Recursive glob match for `*` wildcards (Python `fnmatch` subset used by PF-Core). -/
partial def globMatchChars : List Char → List Char → Bool
  | [], [] => true
  | '*'::pat, uri =>
      globMatchChars pat uri ||
        (match uri with
         | [] => false
         | _::rest => globMatchChars ('*'::pat) rest)
  | p::pat, u::rest =>
      if p = u then globMatchChars pat rest else false
  | _, _ => false

def globMatch (pattern uri : String) : Bool :=
  if pattern = "*" then true else globMatchChars pattern.toList uri.toList

def uriMatchesPattern (uri pattern : String) : Bool :=
  globMatch pattern uri

/--
**Meaning:** Prop-level pattern match for resource URIs against capability patterns.

**Trusted use:** Documentation and parity with runtime `validate_resource_scope`.

**Does not imply:** Lean kernel discharge of resource scope inside trace safety proofs.
-/
def UriMatchesPattern (uri pattern : String) : Prop :=
  globMatch pattern uri = true

def uriMatchesPatternD (uri pattern : String) : Bool :=
  globMatch pattern uri

/--
**Meaning:** URI pattern decider reflects `UriMatchesPattern`.

**Trusted use:** Soundness link for generated audits and cross-language parity tests.

**Does not imply:** Normalization of URI schemes or label-based access control.
-/
theorem uriMatchesPatternD_sound (uri pattern : String) :
    uriMatchesPatternD uri pattern = true ↔ UriMatchesPattern uri pattern := by
  simp [uriMatchesPatternD, UriMatchesPattern, decide_eq_true_iff]

/--
**Meaning:** Resource `r` matches pattern `pat` when its URI satisfies the pattern language.

**Trusted use:** Runtime resource-scope validation parity (`validate_resource_scope`).

**Does not imply:** Tenant alignment or capability authorization.
-/
def ResourceMatchesPattern (r : Resource) (pat : ResourcePattern) : Prop :=
  match pat with
  | ResourcePattern.any => True
  | ResourcePattern.glob pattern => UriMatchesPattern r.uri pattern

def resourceMatchesPatternD (r : Resource) (pat : ResourcePattern) : Bool :=
  match pat with
  | ResourcePattern.any => true
  | ResourcePattern.glob pattern => uriMatchesPatternD r.uri pattern

/--
**Meaning:** Resource pattern decider reflects `ResourceMatchesPattern`.

**Trusted use:** Cross-language parity with Python `resource_matches_pattern`.

**Does not imply:** Lean kernel proof of scope inside `ActionAllowed` / `TraceSafe`.
-/
theorem resourceMatchesPatternD_sound (r : Resource) (pat : ResourcePattern) :
    resourceMatchesPatternD r pat = true ↔ ResourceMatchesPattern r pat := by
  cases pat with
  | any => simp [resourceMatchesPatternD, ResourceMatchesPattern]
  | glob pattern =>
    simp [resourceMatchesPatternD, ResourceMatchesPattern, uriMatchesPatternD_sound]

/-- Catalog patterns used by PF-Core runtime capability table (parity anchor). -/
def catalogResourcePatterns : List ResourcePattern :=
  [ ResourcePattern.glob "/data/*"
  , ResourcePattern.any
  , ResourcePattern.glob "mailto:*"
  , ResourcePattern.glob "agent:*"
  , ResourcePattern.glob "mcp:*"
  , ResourcePattern.glob "lab:*"
  ]

end PFCore
