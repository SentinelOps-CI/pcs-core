# LabTrust v0.1 Profile

## Dependency contract (cross-repo)

| Step | Repo | Output |
|------|------|--------|
| 1 | **LabTrust-Gym** | Pending `ScienceClaimBundle.v0` with `certificates: []` |
| 2 | **CertifyEdge** | `TraceCertificate.v0` |
| 3 | **LabTrust-Gym** | Certified `ScienceClaimBundle.v0` with certificate attached |
| 4 | **Provability Fabric** | Verifies certified bundle and emits `VerificationResult.v0` |
| 5 | **Provability Fabric** | Signs and emits `SignedScienceClaimBundle.v0` |
| 6 | **Scientific Memory** | Imports `SignedScienceClaimBundle.v0` for durable display |

Downstream repositories depend on **pcs-core** for schemas, validation, and hash, vendored schema mirrors remain read-only copies as described in [downstream-schema-sync.md](downstream-schema-sync.md), and all artifacts use `schema_version` value `"v0"` including `SignedScienceClaimBundle.v0`.

## Fixture types

| Directory | Purpose |
|-----------|---------|
| `examples/labtrust/` | Schema conformance fixtures with stable example values for `pcs validate`, continuous integration, and binding tests |
| `examples/labtrust-release/` | Generated release fixtures with end-to-end cross-repo pipeline outputs and `RELEASE_FIXTURE_MANIFEST.json` |

Only `examples/labtrust-release/` serves as PCS v0.1 release evidence, and maintainers regenerate the tree after one cross-repo clean-checkout chain through `just generate-labtrust-release-fixtures` with `PCS_CHAIN_WORK` set, then verify with `pcs validate-release-chain examples/labtrust-release/` or `just validate-labtrust-release-fixtures`.

## Release fixture authority

`examples/labtrust/` is the canonical conformance fixture set, and downstream repositories may copy these fixtures for schema tests when each file stays byte-for-byte identical to pcs-core at the pinned commit with the same rule for schema mirrors in [downstream-schema-sync.md](downstream-schema-sync.md).

`examples/labtrust-release/` is the canonical release fixture set, and the manifest records exact commits for pcs-core, LabTrust-Gym, CertifyEdge, Provability Fabric, and Scientific Memory together with the SHA-256 digest of every release artifact file.

Every repository in the release train copies this directory for local release fixture tests and refreshes it through the full materialize workflow instead of regenerating partial fixtures independently, and canonical pin values with failure codes appear in [labtrust-release-fixtures.md](labtrust-release-fixtures.md).

| Valid fixture | Producer stage |
|---------------|----------------|
| `science_claim_bundle.pending.valid.json` | LabTrust-Gym |
| `trace_certificate.valid.json` | CertifyEdge |
| `science_claim_bundle.certified.valid.json` | LabTrust-Gym |
| `verification_result.valid.json` | Provability Fabric |
| `signed_science_claim_bundle.valid.json` | Provability Fabric through Scientific Memory |

| Invalid fixture | Expected failure |
|-----------------|-------------------|
| `invalid_singular_runtime_receipt_bundle.json` | `runtime_receipt` field instead of `runtime_receipts` array |
| `invalid_signed_schema_version_artifact_name.json` | `schema_version` encodes artifact class |
| `invalid_failed_verification_result.json` | failed checks with import-ready status |
| `invalid_missing_trace_certificate.json` | certified bundle without certificates |

## Repos in scope

| Repo | Role |
|------|------|
| [pcs-core](https://github.com/SentinelOps-CI/pcs-core) | Canonical schemas, validation, hash |
| [LabTrust-Gym](https://github.com/fraware/LabTrust-Gym) | Simulation, receipts, bundle export |
| [CertifyEdge](https://github.com/fraware/CertifyEdge) | `TraceCertificate.v0` |
| [provability-fabric](https://github.com/SentinelOps-CI/provability-fabric) | Verify and sign |
| [scientific-memory](https://github.com/fraware/scientific-memory) | Import and render |

## PCS v0.1 clean-checkout chain (release gate)

PCS v0.1 is release-ready when the full cross-repo chain succeeds from a LabTrust-Gym checkout with sibling repositories for pcs-core, CertifyEdge, provability-fabric, and scientific-memory.

```powershell
$env:PCS_DETERMINISTIC = "1"
& examples\pcs_qc_release\scripts\run_pcs_v01_clean_chain.ps1
```

```bash
export PCS_DETERMINISTIC=1
bash examples/pcs_qc_release/scripts/run_pcs_v01_clean_chain.sh
```

Canonical manual steps and environment variables appear in [LabTrust-Gym `docs/pcs_v01_clean_chain.md`](https://github.com/fraware/LabTrust-Gym/blob/main/docs/pcs_v01_clean_chain.md).

### Manual chain (same commands as the release gate)

```bash
# LabTrust-Gym
PCS_DETERMINISTIC=1 labtrust run-demo qc-release
PCS_DETERMINISTIC=1 labtrust run-demo qc-release-invalid-missing-qc
PCS_DETERMINISTIC=1 labtrust run-demo qc-release-invalid-unauthorized

labtrust export-trace --run runs/qc-release --out trace.json
labtrust export-runtime-receipt --run runs/qc-release --out runtime_receipt.json
labtrust export-pcs --run runs/qc-release --out science_claim_bundle.pending.json
pcs validate science_claim_bundle.pending.json

# CertifyEdge
certifyedge emit-pcs-certificate \
  --spec templates/hospital_lab/qc_release.stl \
  --trace trace.json \
  --out trace_certificate.json
pcs validate trace_certificate.json
certifyedge verify-certificate trace_certificate.json --trace trace.json

# LabTrust-Gym
labtrust attach-certificate \
  --bundle science_claim_bundle.pending.json \
  --certificate trace_certificate.json \
  --out science_claim_bundle.certified.json
pcs validate science_claim_bundle.certified.json

# Provability Fabric
pf verify science-claim science_claim_bundle.certified.json \
  --out verification_result.json
pcs validate verification_result.json

pf sign science-claim science_claim_bundle.certified.json \
  --out signed_science_claim_bundle.json
pcs validate signed_science_claim_bundle.json
pf inspect science-claim signed_science_claim_bundle.json

# Scientific Memory (positional just args)
cd ../scientific-memory
just pcs-import-bundle ../LabTrust-Gym/signed_science_claim_bundle.json
just pcs-render-claim claim-pcs-qc-release-v0.1
```

## pcs-core validation highlights

Unknown `status` values fail validation, `ScienceClaimBundle` requires `assumption_set` and a non-empty `runtime_receipts` array, certified bundles with `CertificateChecked` require at least one `TraceCertificate`, `TraceCertificate.status` must stay within the certificate enum, receipt and certificate `trace_hash` values must align, and zero `source_commit` values fail unless `local_dev` is true on that artifact.

## Simulation disclaimer

All claims in this profile describe simulation artifacts aimed at integration testing and protocol education instead of clinical production systems or production medical certification.
