# LabTrust release fixtures (v0.1)

**Trust loop:** LabTrust-Gym → `RuntimeReceipt.v0` → CertifyEdge `TraceCertificate.v0` → `ScienceClaimBundle.v0` → Provability Fabric `VerificationResult.v0` → `SignedScienceClaimBundle.v0` → Scientific Memory import and rendering.

**Canonical fixtures:** `examples/labtrust-release/` in pcs-core. Downstream repositories must sync this directory at a pinned pcs-core commit or prove canonical-hash equivalence to the manifest. Do not regenerate partial files; refresh only through the full materialize workflow.

| File | Role |
|------|------|
| `RELEASE_FIXTURE_MANIFEST.json` | Artifact hashes and five producer commits |
| `release_manifest.v0.json` | `ReleaseManifest.v0` (digest-signed) |
| `handoff_manifest.*.v0.json` | Stage handoffs for the QC-release chain |
| `release_chain_validation_result.v0.json` | Validator attestation |

Regenerate protocol JSON after promoting fixtures:

```bash
just materialize-labtrust-protocol
```

## Verify

```bash
pcs validate-release-chain examples/labtrust-release/
just validate-labtrust-release-fixtures
```

CI runs `pcs validate-release-chain` on every push.

## `pcs validate-release-chain` (30 checks)

| # | Check |
|---|--------|
| 1 | `RELEASE_FIXTURE_MANIFEST.json` exists |
| 2 | Every manifest-listed artifact file exists |
| 3 | Every artifact hash matches the manifest |
| 4 | No `local_dev`, zero commits, or placeholder commits in artifacts |
| 5 | `runtime_receipt.json` `source_commit` = `manifest.labtrust_gym_commit` |
| 6–8 | LabTrust `source_commit` in pending, certified, and nested signed bundles |
| 9–10 | CertifyEdge `source_commit` in trace certificate and bundles |
| 11–12 | Provability Fabric commits in verification and signed bundle |
| 13–14 | Scientific Memory report commits |
| 15–19 | `certificate_id` alignment across chain |
| 20 | `trace_hash` identical across trace, receipt, certificate, verification, signed bundle |
| 21–22 | Verified and signed input bundle hashes match manifest |
| 23–26 | Scientific Memory import: `passed`, `strict=true`, `allow_legacy=false`, `bundle_shape=pcs_core` |

## Failure codes

`manifest_missing`, `manifest_hash_mismatch`, `artifact_missing`, `schema_validation_failed`, `placeholder_commit_detected`, `labtrust_commit_mismatch`, `certifyedge_commit_mismatch`, `pf_commit_mismatch`, `scientific_memory_commit_mismatch`, `certificate_id_mismatch`, `trace_hash_mismatch`, `verified_input_hash_mismatch`, `signed_input_hash_mismatch`, `scientific_memory_import_failed`, `legacy_import_detected`

Constants: `pcs_core.release_canonical`.

See also [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md) and [downstream-schema-sync.md](downstream-schema-sync.md).
