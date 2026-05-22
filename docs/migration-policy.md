# Migration policy (v0.1)

## Principles

1. **pcs-core owns schemas** — downstream repos vendor or submodule; they do not fork shapes.
2. **Migration is explicit** — every transform emits a machine-readable report.
3. **Release mode is strict** — migrations that weaken provenance or hashes are rejected for release tags.

## Change classes

| Class | Examples | Consumer impact |
|-------|----------|-----------------|
| Patch | Schema descriptions, optional non-release fields | Re-validate; usually no migration |
| Minor | New optional fields, new checks satisfied by existing artifacts | Re-validate |
| Breaking | Removed fields, narrowed enums, new hash rules | Migration required |

## Deprecation

Breaking changes require:

1. A release note under `docs/releases/`
2. `ArtifactRegistry.v0` entries marked `Deprecated`
3. A documented `pcs migrate` path

## `pcs migrate`

```bash
pcs migrate --from v0 --to v0 examples/runtime_receipt.valid.json
```

v0.1 provides **identity migration** for `v0 → v0` (validation report only). Other version pairs error until a future protocol version ships.

## LabTrust release manifests

`examples/labtrust-release/` maintains two synchronized views:

| File | Used by |
|------|---------|
| `RELEASE_FIXTURE_MANIFEST.json` | `pcs validate-release-chain` digest checks |
| `release_manifest.v0.json` | `ReleaseManifest.v0` protocol tooling |

Regenerate both together via `just materialize-labtrust-protocol`.

## Migration reports

Reports include `from_version`, `to_version`, `artifact_type`, `changes`, and `status` (`noop` or `migrated`).

See also [versioning.md](versioning.md) and [status-transition-policy.md](status-transition-policy.md).
