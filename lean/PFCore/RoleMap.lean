import PFCore.Capability
import PFCore.Catalog

/-!
# PF-Core role-to-capability expansion (conservative kernel subset)

Lean `HasCapability` inspects `principal.capabilities` only. Runtime compilation expands
known roles into explicit capability ids. This module models that expansion map and proves
alignment between expanded role capabilities and explicit principal capability lists.

Full runtime RoleMap parity and dynamic role assignment remain outside the kernel; see
`docs/pf-core/assumptions.md`. Role map entries are generated into
`Catalog.runtimeRoleMapEntries` from `catalog/pf_core.catalog.json`.
-/

namespace PFCore

/-- Static role-to-capability map (mirrors runtime `ROLE_CAPABILITY_MAP` conceptually). -/
structure RoleMap where
  entries : List (String × List String)

/-- Lookup capabilities granted by a single role name (empty when role is unknown). -/
def RoleMap.lookup (rm : RoleMap) (role : String) : List String :=
  match rm.entries.find? (fun p => p.1 = role) with
  | some (_, caps) => caps
  | none => []

/-- Flatten role names into capability ids via `RoleMap.lookup`. -/
def RoleMap.expandRoles (rm : RoleMap) (roles : List String) : List String :=
  roles.flatMap (rm.lookup)

/--
**Meaning:** Expanded principal capabilities: role expansion plus explicit capabilities,
deduplicated in list order (roles first, then explicit extras).

**Trusted use:** Modeling runtime `expand_principal_capabilities` for alignment proofs.

**Does not imply:** Runtime producers emit aligned principals without compiler enforcement.
-/
def RoleMap.expandPrincipal (rm : RoleMap) (p : Principal) : List String :=
  let fromRoles := rm.expandRoles p.roles
  fromRoles ++ p.capabilities.filter (fun cap => cap ∉ fromRoles)

/--
**Meaning:** Principal explicit capabilities match role expansion under `rm`.

**Trusted use:** Precondition for lean-check alignment and `HasCapability` discharge.

**Does not imply:** Roles were validated at runtime or unknown roles were rejected.
-/
def PrincipalCapabilitiesAligned (rm : RoleMap) (p : Principal) : Prop :=
  p.capabilities = rm.expandPrincipal p

/--
**Meaning:** Every capability assigned to a role in the map appears in role expansion.

**Trusted use:** Sanity check for map entries used in alignment proofs.

**Does not imply:** The role name is assigned to any concrete principal.
-/
theorem role_lookup_in_expandRoles (rm : RoleMap) (role cap : String) :
    cap ∈ rm.lookup role → cap ∈ rm.expandRoles [role] := by
  intro hmem
  unfold RoleMap.expandRoles
  rw [List.mem_flatMap]
  exact ⟨role, List.mem_singleton_self role, hmem⟩

/--
**Meaning:** Capabilities from role lookup are included in full principal expansion.

**Trusted use:** Connecting single-role grants to `expandPrincipal`.

**Does not imply:** Unknown roles contribute capabilities (lookup is empty).
-/
theorem role_lookup_in_expandPrincipal (rm : RoleMap) (p : Principal) (role cap : String) :
    role ∈ p.roles → cap ∈ rm.lookup role → cap ∈ rm.expandPrincipal p := by
  intro hrole hcap
  have hExpand : cap ∈ rm.expandRoles p.roles := by
    simp [RoleMap.expandRoles, List.mem_flatMap]
    exact ⟨role, hrole, hcap⟩
  unfold RoleMap.expandPrincipal
  exact List.mem_append_left _ hExpand

/--
**Meaning:** When principal capabilities are aligned with role expansion, membership in
the expanded set implies `HasCapability`.

**Trusted use:** Bridge from runtime role expansion to Lean `HasCapability` on aligned traces.

**Does not imply:** Unaligned principals satisfy capability checks or role expansion at runtime.
-/
theorem aligned_principal_has_capability (rm : RoleMap) (p : Principal) (cap : String) :
    PrincipalCapabilitiesAligned rm p → cap ∈ rm.expandPrincipal p → HasCapability p cap := by
  intro hAlign hmem
  rw [HasCapability, hAlign]
  exact hmem

/--
**Meaning:** Aligned principals hold every capability contributed by a mapped role on the principal.

**Trusted use:** Discharging capability requirements after role expansion alignment.

**Does not imply:** Action allowance, tenant scope, or effect compatibility.
-/
theorem aligned_role_capability_granted (rm : RoleMap) (p : Principal) (role cap : String) :
    PrincipalCapabilitiesAligned rm p → role ∈ p.roles → cap ∈ rm.lookup role →
    HasCapability p cap := by
  intro hAlign hrole hcap
  exact aligned_principal_has_capability rm p cap hAlign
    (role_lookup_in_expandPrincipal rm p role cap hrole hcap)

/-- Union of all capability ids listed in a role map (deduplicated list order). -/
def RoleMap.allMappedCapabilities (rm : RoleMap) : List String :=
  rm.entries.flatMap (fun p => p.2)

/--
**Meaning:** Static runtime role map mirroring Python `ROLE_CAPABILITY_MAP` keys and values.

**Trusted use:** Cross-language parity audits and `runtime_role_expansion_subset`.

**Does not imply:** Runtime producers assign only these roles — entries are generated from
`catalog/pf_core.catalog.json` into `Catalog.runtimeRoleMapEntries`.
-/
def runtimeRoleMap : RoleMap :=
  { entries := Catalog.runtimeRoleMapEntries }

/-- Role names in `runtimeRoleMap` (mirrors Python `ROLE_CAPABILITY_MAP` keys). -/
def runtimeRoleMapKeys : List String :=
  runtimeRoleMap.entries.map (fun p => p.1)

private theorem lookupMem_flatMap (entries : List (String × List String)) (role cap : String)
    (hmem :
      cap ∈
        match entries.find? (fun p => p.1 = role) with
        | some (_, cs) => cs
        | none => []) :
    cap ∈ entries.flatMap (fun p => p.2) := by
  induction entries with
  | nil => simp at hmem
  | cons head tail ih =>
    by_cases hname : head.1 = role
    · subst hname
      simp at hmem
      rw [List.flatMap_cons, List.mem_append]
      exact Or.inl hmem
    · simp [hname] at hmem
      rw [List.flatMap_cons, List.mem_append]
      exact Or.inr (ih hmem)

theorem lookup_in_allMappedCapabilities (rm : RoleMap) (role cap : String) :
    cap ∈ rm.lookup role → cap ∈ rm.allMappedCapabilities := by
  intro hmem
  rw [RoleMap.allMappedCapabilities]
  unfold RoleMap.lookup at hmem
  exact lookupMem_flatMap rm.entries role cap hmem

/--
**Meaning:** Role expansion only yields capability ids present in the static map union.

**Trusted use:** Bounding runtime role expansion; audit parity with Python catalog.

**Does not imply:** Unknown roles contribute capabilities (lookup is empty) or principals are aligned.
-/
theorem runtime_role_expansion_subset (roles : List String) (cap : String) :
    cap ∈ runtimeRoleMap.expandRoles roles → cap ∈ runtimeRoleMap.allMappedCapabilities := by
  intro hmem
  simp [RoleMap.expandRoles, List.mem_flatMap] at hmem
  rcases hmem with ⟨role, _, hlookup⟩
  exact lookup_in_allMappedCapabilities runtimeRoleMap role cap hlookup

end PFCore

