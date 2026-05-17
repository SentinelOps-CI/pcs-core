# pcs-v0.1.0-rc1 release checklist

## Release objective

Prove the PCS v0.1 trust loop is **complete**, **reproducible**, **schema-validated**, and **protected against fixture drift** for a single simulated LabTrust QC-release workflow. This RC does not add new artifact families, demos, or protocol abstractions.

## Artifact chain

```
LabTrust-Gym runtime trace (trace.json)
  → RuntimeReceipt.v0
  → CertifyEdge TraceCertificate.v0
  → ScienceClaimBundle.v0 (pending → certified)
  → Provability Fabric VerificationResult.v0
  → SignedScienceClaimBundle.v0
  → Scientific Memory import report
```

**Canonical fixtures:** `examples/labtrust-release/` with `RELEASE_FIXTURE_MANIFEST.json`.

## Validate (exact commands)

From repo root after `pip install -e python/.[dev]`:

```bash
pcs validate-release-chain examples/labtrust-release/
pcs validate-release-chain examples/labtrust-release/ --json
just validate-labtrust-release-fixtures
cd python && pytest -q tests/test_release_chain.py
```

CI runs `pcs validate-release-chain ../examples/labtrust-release/` on every push and on PRs touching schemas, release fixtures, `python/pcs_core/`, or `docs/labtrust-v0.1-profile.md`.

## Canonical manifest (current `main`)

| Field | Value |
|-------|--------|
| `release_candidate` | `pcs-v0.1.0-rc1` |
| `labtrust_gym_commit` | `4c5439ae358733f9a4c4a58e33fdaed1ab0d29de` |
| `certifyedge_commit` | `cb6848001e2e60a484e04eba5ad6be3fe2e4eccc` |
| `provability_fabric_commit` | `0f659b90c80c46a6bbfd51b0d37ea723b032fb9d` |
| `scientific_memory_commit` | `67498ff14325d08ecbbc94b8d41647d9cd79c309` |
| `science_claim_bundle.certified.json` | `sha256:9b42d792199eb6f358d26f822699f0ed65bb4366eee306d4958d42121c656833` |
| `certificate_id` | `cert-trace-886c95f0-5d63-42d6-aa13-5891c12c5a6a` |
| `trace_hash` | `sha256:c3e8a3dc4ad86d533de1dfa4ae7fe2a338c2cff3c945404c96a75216524d58cd` |

Full digests: see `examples/labtrust-release/RELEASE_FIXTURE_MANIFEST.json`.

## Downstream sync

1. Pin pcs-core at the RC tag commit.
2. Copy `examples/labtrust-release/` into the downstream repo’s test fixture path **or** verify canonical-hash equivalence with `pcs validate-release-chain` on the copy.
3. Do **not** regenerate partial fixtures; refresh only when pcs-core promotes a new atomic chain.

## Invalid fixtures (negative tests)

Under `examples/labtrust-release-invalid/`:

| Directory | Fails with |
|-----------|------------|
| `placeholder_commit/` | `placeholder_commit_detected` |
| `mismatched_certificate_id/` | `certificate_id_mismatch` |
| `mismatched_trace_hash/` | `trace_hash_mismatch` |
| `mismatched_certified_bundle_hash/` | `verified_input_hash_mismatch` |
| `failed_scientific_memory_import/` | `scientific_memory_import_failed` |
| `legacy_import_mode/` | `legacy_import_detected` |

Regenerate copies from canonical: `python scripts/materialize_invalid_release_fixtures.py`.

## Known limitations

- Single demo domain (hospital lab QC-release simulation).
- `trace.json` and `scientific_memory_import_report.json` use structural RC checks; not all auxiliary files have PCS JSON Schemas yet.
- Lean formalization deferred until after v0.1 RC lock.

## Non-claims

PCS v0.1 does **not** claim clinical validity.

PCS v0.1 does **not** certify a production hospital system.

PCS v0.1 does **not** formally prove all lab semantics.

PCS v0.1 demonstrates a **proof-carrying simulated lab workflow** with machine-checkable artifacts, hash-linked bundles, and cross-repo provenance pins.

## Tag readiness

- [ ] `pcs validate-release-chain examples/labtrust-release/` passes locally
- [ ] CI green on `main`
- [ ] Downstream repos synced or hash-verified against this manifest
- [ ] Tag `pcs-v0.1.0-rc1` on the pinned `pcs_core_commit` recorded in the manifest
