# PCS versioning (v0.1)

## Schema version field

All PCS artifacts use `schema_version: "v0"` for the v0.1 release. Pin git tag **`v0.1.0`** on pcs-core to fix schemas, registry, and validators at one commit.

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

Release protocol artifacts (`ReleaseManifest.v0`, `HandoffManifest.v0`, `ReleaseChainValidationResult.v0`, `ArtifactRegistry.v0`) use the same `schema_version: "v0"`. Their `registry_version` or `release_candidate` fields identify which pcs-core release produced them. See [release-protocol.md](release-protocol.md).
