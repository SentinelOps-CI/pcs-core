# PCS versioning (v0.1)

## Schema version field

All PCS artifacts use `schema_version` value `"v0"` for the v0.1 release, and pinning git tag **`v0.1.0`** on pcs-core fixes schemas, registry, and validators at one commit.

## Change classes

| Class | Description | Consumer impact |
|-------|-------------|-----------------|
| **Patch** | Clarify descriptions, add optional fields, tighten validation without changing valid documents | Re-validate existing artifacts with migration usually unnecessary |
| **Minor** | Add optional fields or statuses with backward-compatible semantics | Re-validate; migration optional |
| **Breaking** | Remove fields, rename fields, or narrow enums | Migration required; old artifacts become `Deprecated` |

## Release-mode restrictions

Release mode described in [migration-policy.md](migration-policy.md) requires real git commits without `local_dev`, rejects zero and pattern placeholder commits, requires manifest hashes to match file contents, and accepts only registry-allowed status values.

## Protocol artifacts

Release protocol artifacts (`ReleaseManifest.v0`, `HandoffManifest.v0`, `ReleaseChainValidationResult.v0`, `ArtifactRegistry.v0`) use the same `schema_version` value `"v0"`, and their `registry_version` or `release_candidate` fields identify which pcs-core release produced them as described in [release-protocol.md](release-protocol.md).
