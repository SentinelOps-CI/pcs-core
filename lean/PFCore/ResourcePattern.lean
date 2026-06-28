import PFCore.Action
import PFCore.Catalog
import PFCore.Event
import PFCore.Resource
import PFCore.Theorems

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

def capabilityPatternFor (cap : String) : ResourcePattern :=
  ResourcePattern.ofString (Catalog.capabilityPatternString cap)

/-- Recursive glob match for `*` wildcards (catalog URI patterns in PF-Core). -/
def globMatchCharsFuel : Nat → List Char → List Char → Bool
  | 0, _, _ => false
  | _ + 1, [], [] => true
  | fuel + 1, '*' :: pat, uri =>
      globMatchCharsFuel fuel pat uri ||
        (match uri with
         | [] => false
         | _ :: rest => globMatchCharsFuel fuel ('*' :: pat) rest)
  | fuel + 1, p :: pat, u :: rest =>
      if p = u then globMatchCharsFuel fuel pat rest else false
  | _, _, _ => false

def globMatchChars (pat uri : List Char) : Bool :=
  globMatchCharsFuel (pat.length + uri.length + 1) pat uri

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

/--
**Meaning:** Resource `r` URI matches the catalog pattern bound to capability `cap`.

**Trusted use:** Runtime `validate_resource_scope` parity; certificate
`contract_semantics_checked.runtime` (`resource_pattern_scope`).

**Does not imply:** Lean kernel discharge inside `ActionAdmissible` without runtime check.
-/
def ResourceWithinCapabilityPattern (r : Resource) (cap : String) : Prop :=
  ResourceMatchesPattern r (capabilityPatternFor cap)

def resourceWithinCapabilityPatternD (r : Resource) (cap : String) : Bool :=
  resourceMatchesPatternD r (capabilityPatternFor cap)

/--
**Meaning:** Decider reflects `ResourceWithinCapabilityPattern` for catalog capabilities.

**Trusted use:** Cross-language parity and certificate runtime semantics recording.

**Does not imply:** Automatic inclusion in `TraceSafe` without runtime validation.
-/
theorem resourceWithinCapabilityPatternD_sound (r : Resource) (cap : String) :
    resourceWithinCapabilityPatternD r cap = true ↔ ResourceWithinCapabilityPattern r cap := by
  simp [resourceWithinCapabilityPatternD, ResourceWithinCapabilityPattern,
    resourceMatchesPatternD_sound]

/-- Every resource in `resources` matches the catalog pattern for capability `cap`. -/
def ResourcesWithinCapabilityPattern (resources : List Resource) (cap : String) : Prop :=
  ∀ r ∈ resources, ResourceWithinCapabilityPattern r cap

def resourcesWithinCapabilityPatternD (resources : List Resource) (cap : String) : Bool :=
  resources.all (fun r => resourceWithinCapabilityPatternD r cap)

theorem resourcesWithinCapabilityPatternD_sound (resources : List Resource) (cap : String) :
    resourcesWithinCapabilityPatternD resources cap = true ↔
      ResourcesWithinCapabilityPattern resources cap := by
  simp [resourcesWithinCapabilityPatternD, ResourcesWithinCapabilityPattern,
    List.all_eq_true, resourceWithinCapabilityPatternD_sound]

/-- Read/write footprint URIs match the catalog pattern for action capability `cap`. -/
def ActionResourcesWithinCapabilityPattern
    (reads writes : List Resource) (cap : String) : Prop :=
  ResourcesWithinCapabilityPattern reads cap ∧
    ResourcesWithinCapabilityPattern writes cap

def actionResourcesWithinCapabilityPatternD
    (reads writes : List Resource) (cap : String) : Bool :=
  resourcesWithinCapabilityPatternD reads cap &&
    resourcesWithinCapabilityPatternD writes cap

/--
**Meaning:** Action resource-scope decider reflects read/write pattern membership.

**Trusted use:** Generated proof obligations and runtime `validate_resource_scope` parity.

**Does not imply:** Discharge inside `ActionAdmissible` / `TraceSafe` without explicit obligations.
-/
theorem actionResourcesWithinCapabilityPatternD_sound
    (reads writes : List Resource) (cap : String) :
    actionResourcesWithinCapabilityPatternD reads writes cap = true ↔
      ActionResourcesWithinCapabilityPattern reads writes cap := by
  simp [actionResourcesWithinCapabilityPatternD, ActionResourcesWithinCapabilityPattern,
    resourcesWithinCapabilityPatternD_sound, Bool.and_eq_true]

/--
**Meaning:** Kernel admissibility extended with catalog resource-pattern scope (decidable subset).

**Trusted use:** Lean-check bridge for runtime `validate_resource_scope`; not part of kernel `TraceSafe`.

**Does not imply:** Full glob pattern discharge for arbitrary URIs outside the catalog subset.
-/
def ActionAdmissibleWithResourcePattern (p : Principal) (a : Action) : Prop :=
  ActionAdmissible p a ∧
    ActionResourcesWithinCapabilityPattern a.reads a.writes a.capability

def actionAdmissibleWithResourcePatternD (p : Principal) (a : Action) : Bool :=
  actionAdmissibleD p a &&
    actionResourcesWithinCapabilityPatternD a.reads a.writes a.capability

/--
**Meaning:** Extended admissibility decider matches Prop-level resource-pattern bridge predicate.

**Trusted use:** Generated `concrete_action_resource_scope_*` proofs and runtime decider alignment.

**Does not imply:** Inclusion in kernel `EventSafe` / `TraceSafe` without explicit obligations.
-/
theorem actionAdmissibleWithResourcePatternD_sound (p : Principal) (a : Action) :
    actionAdmissibleWithResourcePatternD p a = true ↔
      ActionAdmissibleWithResourcePattern p a := by
  simp [actionAdmissibleWithResourcePatternD, ActionAdmissibleWithResourcePattern,
    actionAdmissibleD_sound, actionResourcesWithinCapabilityPatternD_sound, Bool.and_eq_true]

/--
**Meaning:** Resource-pattern bridge implies kernel `ActionAdmissible` (strictness is one-way).

**Trusted use:** Honest boundary: runtime scope discharge is stronger than kernel allowance alone.

**Does not imply:** `TraceSafe` already includes resource-pattern scope.
-/
theorem actionAdmissibleWithResourcePattern_implies_actionAdmissible (p : Principal) (a : Action)
    (h : ActionAdmissibleWithResourcePattern p a) : ActionAdmissible p a :=
  h.left

/--
**Meaning:** When resource-pattern scope holds, allowed safe events satisfy extended admissibility.

**Trusted use:** Links per-event generated scope proofs to bridge predicate for allow events.

**Does not imply:** Denied events or covert channels are resource-scoped or NI-safe.
-/
theorem eventSafe_allow_with_resourcePattern (ev : Event) (h : EventSafe ev)
    (hallow : ev.decision = Decision.allow)
    (hscope : ActionResourcesWithinCapabilityPattern ev.action.reads ev.action.writes
      ev.action.capability) :
    ActionAdmissibleWithResourcePattern ev.principal ev.action := by
  refine ⟨allowed_event_has_allowed_action ev h hallow, hscope⟩

/--
**Meaning:** Runtime decider alignment: extended admissibility implies kernel admissibility.

**Trusted use:** Certificate `contract_semantics_checked` bridge documentation.

**Does not imply:** Lean kernel `TraceSafe` discharge of resource patterns without codegen obligations.
-/
theorem actionAdmissibleWithResourcePatternD_implies_actionAdmissible (p : Principal) (a : Action)
    (h : actionAdmissibleWithResourcePatternD p a = true) :
    ActionAdmissible p a :=
  actionAdmissibleWithResourcePattern_implies_actionAdmissible p a
    ((actionAdmissibleWithResourcePatternD_sound p a).mp h)

/--
**Meaning:** Kernel resource-pattern admissibility (`ActionAdmissibleR`) extends
`ActionAdmissible` with catalog URI/glob scope on read/write footprints.

**Trusted use:** Stronger TraceSafe chain variant (`TraceSafeR`) without changing base `TraceSafe`.

**Does not imply:** Arbitrary URI patterns outside the catalog glob subset (`globMatchCharsFuel`).
-/
abbrev ActionAdmissibleR (p : Principal) (a : Action) : Prop :=
  ActionAdmissibleWithResourcePattern p a

def actionAdmissibleRD (p : Principal) (a : Action) : Bool :=
  actionAdmissibleWithResourcePatternD p a

theorem actionAdmissibleRD_sound (p : Principal) (a : Action) :
    actionAdmissibleRD p a = true ↔ ActionAdmissibleR p a := by
  exact actionAdmissibleWithResourcePatternD_sound p a

/--
**Meaning:** Allowed events are safe under resource-pattern admissibility.

**Trusted use:** Per-event kernel discharge in `TraceSafeR` / codegen `eventSafeRD`.

**Does not imply:** Denied events were resource-scoped or policy-correct.
-/
def EventSafeR (ev : Event) : Prop :=
  ev.decision = Decision.allow → ActionAdmissibleR ev.principal ev.action

def eventSafeRD (ev : Event) : Bool :=
  match ev.decision with
  | Decision.deny => true
  | Decision.allow => actionAdmissibleRD ev.principal ev.action

theorem eventSafeRD_sound (ev : Event) :
    eventSafeRD ev = true ↔ EventSafeR ev := by
  cases ev with
  | mk _ p a d =>
    cases d <;>
    simp [eventSafeRD, EventSafeR, actionAdmissibleRD_sound, actionAdmissibleWithResourcePatternD_sound]

/--
**Meaning:** Resource-pattern trace safety: every event satisfies `EventSafeR`.

**Trusted use:** Migration target for kernel resource discharge; implies base `TraceSafe`.

**Does not imply:** Full glob language parity with Python `fnmatch` for all patterns.
-/
def TraceSafeR : Trace → Prop
  | Trace.empty => True
  | Trace.cons tr ev => TraceSafeR tr ∧ EventSafeR ev

def traceSafeRD : Trace → Bool
  | Trace.empty => true
  | Trace.cons tr ev => traceSafeRD tr && eventSafeRD ev

theorem traceSafeRD_sound (tr : Trace) :
    traceSafeRD tr = true ↔ TraceSafeR tr := by
  induction tr with
  | empty => simp [traceSafeRD, TraceSafeR]
  | cons tr ev ih =>
    simp [traceSafeRD, TraceSafeR, eventSafeRD_sound, ih, and_left_comm]

/--
**Meaning:** `ActionAdmissibleR` implies kernel `ActionAdmissible` (one-way strictness).

**Trusted use:** Honest boundary: `TraceSafeR` refines `TraceSafe` without overclaiming reverse.

**Does not imply:** Base `TraceSafe` already includes resource-pattern scope.
-/
theorem actionAdmissibleR_implies_actionAdmissible (p : Principal) (a : Action)
    (h : ActionAdmissibleR p a) : ActionAdmissible p a :=
  actionAdmissibleWithResourcePattern_implies_actionAdmissible p a h

/--
**Meaning:** `EventSafeR` implies base `EventSafe`.

**Trusted use:** Lifting resource-pattern event safety into the standard kernel chain.

**Does not imply:** Reverse implication without explicit resource-pattern evidence.
-/
theorem eventSafeR_implies_eventSafe (ev : Event) (h : EventSafeR ev) : EventSafe ev := by
  intro hallow
  cases hdec : ev.decision with
  | deny => rw [hdec] at hallow; cases hallow
  | allow => exact actionAdmissibleR_implies_actionAdmissible ev.principal ev.action (h hdec)

/--
**Meaning:** `TraceSafeR` implies base `TraceSafe`.

**Trusted use:** Primary migration link: resource-pattern discharge refines kernel trace safety.

**Does not imply:** `LeanKernelChecked` on legacy traces without `traceSafeRD` obligations.
-/
theorem traceSafeR_implies_traceSafe : ∀ tr, TraceSafeR tr → TraceSafe tr
  | Trace.empty => fun _ => traceSafe_empty
  | Trace.cons tr' ev => fun h =>
    have ⟨hTr, hEv⟩ := h
    ⟨traceSafeR_implies_traceSafe tr' hTr, eventSafeR_implies_eventSafe ev hEv⟩

/--
**Meaning:** Allowed `EventSafeR` events satisfy catalog resource-pattern scope on footprint.

**Trusted use:** Kernel discharge of `ActionResourcesWithinCapabilityPattern` for allow events.

**Does not imply:** Denied events or unknown catalog capabilities are pattern-scoped.
-/
theorem eventSafeR_allow_implies_resource_pattern (ev : Event) (h : EventSafeR ev)
    (hallow : ev.decision = Decision.allow) :
    ActionResourcesWithinCapabilityPattern ev.action.reads ev.action.writes
      ev.action.capability := by
  exact (h hallow).right

/--
**Meaning:** Allowed safe events with explicit scope imply `ActionAdmissibleR` (bridge lemma).

**Trusted use:** Links runtime/codegen scope proofs to kernel `EventSafeR`.

**Does not imply:** `EventSafe` alone discharges resource patterns without scope evidence.
-/
theorem eventSafeR_allow_with_resourcePattern (ev : Event) (h : EventSafeR ev)
    (hallow : ev.decision = Decision.allow) :
    ActionAdmissibleR ev.principal ev.action :=
  h hallow

/--
**Meaning:** `EventSafe` allow plus resource-pattern scope yields `EventSafeR`.

**Trusted use:** Promoting runtime-validated scope into kernel `EventSafeR` when present.

**Does not imply:** Automatic promotion without scope hypothesis.
-/
theorem eventSafe_allow_and_scope_implies_eventSafeR (ev : Event) (h : EventSafe ev)
    (hallow : ev.decision = Decision.allow)
    (hscope : ActionResourcesWithinCapabilityPattern ev.action.reads ev.action.writes
      ev.action.capability) :
    EventSafeR ev := by
  intro hallow'
  exact ⟨allowed_event_has_allowed_action ev h hallow, hscope⟩

/--
**Meaning:** `traceSafeRD` implies base `traceSafeD` (decider refinement).

**Trusted use:** Runtime/codegen alignment: resource-pattern decider is stricter than kernel decider.

**Does not imply:** Python `action_admissible_d` parity without catalog URI mapping.
-/
theorem traceSafeRD_implies_traceSafeD (tr : Trace) (h : traceSafeRD tr = true) :
    traceSafeD tr = true := by
  exact (traceSafeD_sound tr).mpr (traceSafeR_implies_traceSafe tr ((traceSafeRD_sound tr).mp h))

/--
**Meaning:** Universal pattern `*` is kernel-dischargeable for any URI.

**Trusted use:** Documents catalog `cap:network` (`*`) discharge via `globMatch`.

**Does not imply:** Full `fnmatch` (`?`, `[` classes, `**`) or URI normalization.
-/
theorem uriMatchesPattern_star (uri : String) :
    UriMatchesPattern uri "*" := by
  simp [UriMatchesPattern, globMatch, globMatchChars, globMatchCharsFuel]

end PFCore
