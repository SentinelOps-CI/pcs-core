# PCS v0.1 LabTrust release-candidate (canonical)

**Release candidate:** `pcs-v0.1.0-rc1`

**Trust loop:** LabTrust-Gym → `RuntimeReceipt.v0` → CertifyEdge `TraceCertificate.v0` → `ScienceClaimBundle.v0` → Provability Fabric `VerificationResult.v0` → `SignedScienceClaimBundle.v0` → Scientific Memory import and rendering.

**Authority:** `examples/labtrust-release/` in [pcs-core](https://github.com/SentinelOps-CI/pcs-core) is the canonical PCS v0.1 RC fixture chain.

- `RELEASE_FIXTURE_MANIFEST.json` — legacy manifest (hashes + five producer commits)
- `release_manifest.v0.json` — `ReleaseManifest.v0` (same pins, digest-signed)
- `handoff_manifest.*.v0.json` — stage handoffs for the QC-release chain
- `release_chain_validation_result.v0.json` — validator attestation

Regenerate protocol JSON after promoting fixtures: `just materialize-labtrust-protocol`.

Downstream repos must **sync against this directory** at the pinned pcs-core commit or **prove canonical-hash equivalence** to the manifest. Do not regenerate partial fixtures. Refresh only via the full atomic clean-checkout chain and promote into `examples/labtrust-release/`.

## Verification

```bash
pcs validate-release-chain examples/labtrust-release/
just validate-labtrust-release-fixtures
```

CI runs `pcs validate-release-chain` on every push to `main`.

## `pcs validate-release-chain` (30 checks)

| # | Check |
|---|--------|
| 1 | `RELEASE_FIXTURE_MANIFEST.json` exists |
| 2 | Every manifest-listed artifact file exists |
| 3 | Every artifact hash matches the manifest |
| 4 | No `local_dev`, zero commits, or placeholder commits in artifacts |
| 5 | `runtime_receipt.json` `source_commit` = `manifest.labtrust_gym_commit` |
| 6 | All LabTrust `source_commit` in `science_claim_bundle.pending.json` |
| 7 | All LabTrust `source_commit` in `science_claim_bundle.certified.json` |
| 8 | All LabTrust `source_commit` in nested `signed_science_claim_bundle.science_claim_bundle` |
| 9 | `trace_certificate.json` `source_commit` = `manifest.certifyedge_commit` |
| 10 | All CertifyEdge `source_commit` in certified and signed bundles |
| 11 | `verification_result.json` `source_commit` = `manifest.provability_fabric_commit` |
| 12 | `signed_science_claim_bundle.json` `source_commit` = `manifest.provability_fabric_commit` |
| 13–14 | Scientific Memory report `source_commit` and `scientific_memory_commit` |
| 15–19 | `certificate_id` alignment (trace cert, certified refs, verification, signed bundle) |
| 20 | `trace_hash` identical across trace, receipt, certificate, verification, signed bundle |
| 21–22 | `verified_input.bundle_hash` and `signed_input_bundle_hash` = manifest certified hash |
| 23–26 | SM import: `verification_status=passed`, `strict=true`, `allow_legacy=false`, `bundle_shape=pcs_core` |

## Machine-readable failure codes

`manifest_missing`, `manifest_hash_mismatch`, `artifact_missing`, `schema_validation_failed`, `placeholder_commit_detected`, `labtrust_commit_mismatch`, `certifyedge_commit_mismatch`, `pf_commit_mismatch`, `scientific_memory_commit_mismatch`, `certificate_id_mismatch`, `trace_hash_mismatch`, `verified_input_hash_mismatch`, `signed_input_hash_mismatch`, `scientific_memory_import_failed`, `legacy_import_detected`

Pin constants: `pcs_core.release_canonical`.

See also [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md) and [downstream-schema-sync.md](downstream-schema-sync.md).
