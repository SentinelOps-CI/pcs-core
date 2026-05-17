# PCS v0.1 LabTrust release-candidate (canonical)

**Authority:** `examples/labtrust-release/` in [pcs-core](https://github.com/SentinelOps-CI/pcs-core) is the single canonical PCS v0.1 release-candidate fixture set.

Downstream repos (LabTrust-Gym, CertifyEdge, Provability Fabric, Scientific Memory) must **copy** these files into their local test fixture paths. Do **not** regenerate partial fixtures independently. The only supported refresh is a full cross-repo clean-checkout chain that promotes atomically into `examples/labtrust-release/`.

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

Python constants: `pcs_core.release_canonical` (used by pcs-core tests).

## Verification

From repo root (after `pip install -e python/.[dev]`):

```bash
pcs validate-release-chain examples/labtrust-release/
```

Or:

```bash
just validate-labtrust-release-fixtures
```

CI runs this on every push to `main`.

## `validate-release-chain` checks

1. `RELEASE_FIXTURE_MANIFEST.json` exists.
2. All listed artifacts exist.
3. All manifest hashes match files (`manifest_hash_mismatch`).
4. No placeholder commits or `local_dev` (`placeholder_commit_detected`).
5. LabTrust `source_commit` values match `manifest.labtrust_gym_commit` (`manifest_labtrust_commit_mismatch`).
6. CertifyEdge `source_commit` values match `manifest.certifyedge_commit` (`manifest_certifyedge_commit_mismatch`).
7. PF `source_commit` values match `manifest.provability_fabric_commit` (`manifest_pf_commit_mismatch`).
8. Scientific Memory report commits match `manifest.scientific_memory_commit` (`manifest_scientific_memory_commit_mismatch`).
9. `certificate_id` alignment across trace certificate, certified bundle (`certificates`, `claim_artifact.certificate_refs`, `evidence_bundle.certificate_refs`), verification `verified_input`, and signed bundle (`mixed_certificate_id`).
10. `verification_result.verified_input.bundle_hash` equals manifest digest for `science_claim_bundle.certified.json` (`verified_input_hash_mismatch`).
11. `signed_science_claim_bundle.signed_input_bundle_hash` equals the same digest (`signed_input_bundle_hash_mismatch`).
12. `scientific_memory_import_report.verification_status` is `passed`.

## Downstream sync policy

1. Copy the full `examples/labtrust-release/` tree (including `RELEASE_FIXTURE_MANIFEST.json`) from the pinned pcs-core commit.
2. Assert the same pin values in repo-specific release fixture tests.
3. Run `pcs validate-release-chain` on the copied directory in downstream CI when feasible.
4. Refresh only when pcs-core publishes a new promoted manifest from an atomic chain run.

See also [labtrust-v0.1-profile.md](labtrust-v0.1-profile.md) and [downstream-schema-sync.md](downstream-schema-sync.md).
