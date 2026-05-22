# Migration policy (v0.1)

## Principles

pcs-core owns schemas, and downstream repositories vendor or submodule copies while keeping shapes aligned with the pinned revision.

Every transform emits a machine-readable migration report so reviewers can audit what changed.

Release mode stays strict, and migrations that weaken provenance or hashes are rejected for release tags.

## Change classes

| Class | Examples | Consumer impact |
|-------|----------|-----------------|
| Patch | Schema descriptions, optional non-release fields | Re-validate with migration usually unnecessary |
| Minor | New optional fields, new checks satisfied by existing artifacts | Re-validate |
| Breaking | Removed fields, narrowed enums, new hash rules | Migration required |

## Deprecation

Breaking changes require a release note under `docs/releases/`, `ArtifactRegistry.v0` entries marked `Deprecated`, and a documented `pcs migrate` path.

## `pcs migrate`

```bash
pcs migrate --from v0 --to v0 examples/runtime_receipt.valid.json
```

v0.1 provides identity migration for `v0 → v0` that emits a validation report only, and other version pairs return an error until a future protocol version ships.

## LabTrust release manifests

`examples/labtrust-release/` maintains two synchronized views.

| File | Used by |
|------|---------|
| `RELEASE_FIXTURE_MANIFEST.json` | `pcs validate-release-chain` digest checks |
| `release_manifest.v0.json` | `ReleaseManifest.v0` protocol tooling |

Regenerate both together through `just materialize-labtrust-protocol`.

## Migration reports

Reports include `from_version`, `to_version`, `artifact_type`, `changes`, and `status` with values `noop` or `migrated`.

See also [versioning.md](versioning.md) and [status-transition-policy.md](status-transition-policy.md).
