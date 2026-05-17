# PCS versioning (v0.1)

## Schema version field

All PCS artifacts use `schema_version: "v0"` for the v0.1 release train. The **release tag** (`pcs-v0.1.0-rc1`) pins the git commit of pcs-core schemas, registry, and validators.

## Change classes

| Class | Description | Consumer impact |
|-------|-------------|-----------------|
| **Patch** | Clarify descriptions, add optional fields, tighten validation without changing valid documents | Re-validate existing artifacts; usually no migration |
| **Minor** | Add optional fields or statuses with backward-compatible semantics | Re-validate; migration optional |
| **Breaking** | Remove fields, rename fields, or narrow enums | Migration required; old artifacts become `Deprecated` |

## Release-mode restrictions

In release mode (see [migration-policy.md](migration-policy.md)):

- `local_dev` is forbidden
- Zero and pattern placeholder commits are forbidden
- Manifest hashes must match file contents
- Only registry-allowed statuses are accepted

## Protocol artifacts

Phase 2 protocol artifacts (`ReleaseManifest.v0`, `HandoffManifest.v0`, `ReleaseChainValidationResult.v0`, `ArtifactRegistry.v0`) version with the same `v0` schema_version field. Their **registry_version** or **release_candidate** strings identify the PCS release train.
