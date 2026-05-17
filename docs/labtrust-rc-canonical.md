# PCS v0.1 LabTrust release-candidate (canonical)

**Authority:** `examples/labtrust-release/` in [pcs-core](https://github.com/SentinelOps-CI/pcs-core) is the canonical PCS v0.1 RC fixture set.

Downstream repos must **copy** these files for local release fixture tests. Do not regenerate partial fixtures independently. Refresh only via a full cross-repo clean-checkout chain that promotes atomically into `examples/labtrust-release/`.

## Canonical pin (pcs-v0.1.0-rc1)

| Field | Value |
|-------|--------|
| `certificate_id` | `cert-trace-886c95f0-5d63-42d6-aa13-5891c12c5a6a` |
| `trace_hash` | `sha256:c3e8a3dc4ad86d533de1dfa4ae7fe2a338c2cff3c945404c96a75216524d58cd` |
| `science_claim_bundle.certified.json` digest | `sha256:9b42d792199eb6f358d26f822699f0ed65bb4366eee306d4958d42121c656833` |
| `labtrust_gym_commit` | `4c5439ae358733f9a4c4a58e33fdaed1ab0d29de` |
| `certifyedge_commit` | `cb6848001e2e60a484e04eba5ad6be3fe2e4eccc` |
| `provability_fabric_commit` | `0f659b90c80c46a6bbfd51b0d37ea723b032fb9d` |
| `scientific_memory_commit` | `d49cbf78837d42883a3c73078f098669e69f5e3d` |

Python constants: `pcs_core.release_canonical`.

## Verification

```bash
pcs validate-release-chain examples/labtrust-release/
just validate-labtrust-release-fixtures
```

CI runs `pcs validate-release-chain` on every push to `main`.

## `pcs validate-release-chain` checks

1. `RELEASE_FIXTURE_MANIFEST.json` exists.
2. Every manifest-listed artifact file exists.
3. Every manifest artifact hash matches the file (`manifest_hash_mismatch`).
4. No placeholder commits or `local_dev` (`placeholder_commit_detected`).
5. `runtime_receipt.source_commit` equals `manifest.labtrust_gym_commit` (`labtrust_commit_mismatch`).
6. All LabTrust `source_commit` values in pending, certified, and signed bundles match the manifest (`labtrust_commit_mismatch`).
7. `trace_certificate.source_commit` equals `manifest.certifyedge_commit` (`certifyedge_commit_mismatch`).
8. All CertifyEdge `source_commit` values in certified and signed bundles match the manifest (`certifyedge_commit_mismatch`).
9. `verification_result.source_commit` equals `manifest.provability_fabric_commit` (`pf_commit_mismatch`).
10. `signed_science_claim_bundle.source_commit` equals `manifest.provability_fabric_commit` (`pf_commit_mismatch`).
11. `scientific_memory_import_report.source_commit` and `scientific_memory_commit` equal `manifest.scientific_memory_commit` (`scientific_memory_commit_mismatch`).
12. `trace_certificate.certificate_id` equals the certified bundle certificate ID (`certificate_id_mismatch`).
13. Certified `claim_artifact` / `evidence_bundle` `certificate_refs` use the same ID (`certificate_id_mismatch`).
14. `verification_result.verified_input.certificate_id` matches (`certificate_id_mismatch`).
15. Embedded signed `science_claim_bundle` certificate ID matches (`certificate_id_mismatch`).
16. `verification_result.verified_input.bundle_hash` equals the manifest certified-bundle hash (`verified_input_hash_mismatch`).
17. `signed_science_claim_bundle.signed_input_bundle_hash` equals the same hash (`signed_input_hash_mismatch`).
18. `scientific_memory_import_report.verification_status` is `passed` (`scientific_memory_import_failed`).

## Failure codes

`manifest_hash_mismatch`, `placeholder_commit_detected`, `labtrust_commit_mismatch`, `certifyedge_commit_mismatch`, `pf_commit_mismatch`, `scientific_memory_commit_mismatch`, `certificate_id_mismatch`, `verified_input_hash_mismatch`, `signed_input_hash_mismatch`, `scientific_memory_import_failed`.

See also [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md) and [downstream-schema-sync.md](downstream-schema-sync.md).
