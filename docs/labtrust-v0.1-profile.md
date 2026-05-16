# LabTrust v0.1 Profile

This profile describes how active v0.1 repos compose the QC-release demonstration.

## Repos

| Repo | Role |
|------|------|
| [pcs-core](https://github.com/SentinelOps-CI/pcs-core) | Schemas, validation, hash |
| [LabTrust-Gym](https://github.com/fraware/LabTrust-Gym) | Simulation, receipts, bundle export |
| [CertifyEdge](https://github.com/fraware/CertifyEdge) | `TraceCertificate.v0` |
| [provability-fabric](https://github.com/SentinelOps-CI/provability-fabric) | Verify and sign |
| [scientific-memory](https://github.com/fraware/scientific-memory) | Import and render |

## Command sketch

```bash
# LabTrust-Gym
labtrust run-demo qc-release
labtrust export-trace --run runs/qc-release --out trace.json
labtrust export-runtime-receipt --run runs/qc-release --out runtime_receipt.json
labtrust export-pcs --run runs/qc-release --out science_claim_bundle.pending.json

# CertifyEdge
certifyedge emit-pcs-certificate \
  --spec templates/hospital_lab/qc_release.stl \
  --trace trace.json \
  --out trace_certificate.json

# LabTrust-Gym
labtrust attach-certificate \
  --bundle science_claim_bundle.pending.json \
  --certificate trace_certificate.json \
  --out science_claim_bundle.certified.json

# Provability Fabric
pf verify science-claim science_claim_bundle.certified.json
pf sign science-claim science_claim_bundle.certified.json \
  --out signed_science_claim_bundle.json

# Scientific Memory
just pcs-import-bundle BUNDLE=signed_science_claim_bundle.json
just pcs-render-claim CLAIM_ID=<claim_id>
```

## pcs-core obligations for downstream

1. Validate every emitted artifact with `pcs validate` or language bindings.
2. Use canonical status strings only.
3. Compute hashes with `pcs hash` rules.
4. Never redefine artifact types locally.
5. Label UI with guarantee-type separation (see [trust-model.md](trust-model.md)).

## Simulation disclaimer

All claims in this profile are about **simulation artifacts**. Assumption sets must include domain assumptions that exclude clinical production guarantees.
