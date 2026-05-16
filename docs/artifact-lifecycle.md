# Artifact Lifecycle (v0.1)

## Canonical status enum

All repos use the same status strings:

`Draft`, `Extracted`, `HumanReviewed`, `Formalized`, `ProofPending`, `ProofChecked`, `CertificatePending`, `CertificateChecked`, `RuntimeObserved`, `RuntimeChecked`, `Rejected`, `EmpiricalOnly`, `Deprecated`, `Stale`

## Demo-critical statuses

| Status | Role |
|--------|------|
| `Draft` | Work in progress |
| `RuntimeObserved` | Run completed; receipt recorded |
| `CertificatePending` | Awaiting CertifyEdge |
| `CertificateChecked` | Certificate attached and valid |
| `Rejected` | Checker or verifier failed |
| `Stale` | Superseded evidence |

## Typical LabTrust v0.1 flow

1. **Run** — LabTrust produces run output; receipt status `RuntimeObserved`.
2. **Export** — `RuntimeReceipt.v0`, `trace.json`, pending `ScienceClaimBundle.v0` (`certificates` may be empty).
3. **Certify** — CertifyEdge emits `TraceCertificate.v0` (`CertificateChecked` or `Rejected`).
4. **Attach** — Bundle updated; claim status moves toward `CertificateChecked`.
5. **Verify & sign** — Provability Fabric emits `VerificationResult.v0`.
6. **Import** — Scientific Memory renders with guarantee-type labels.

## Pending vs certified bundles

- **Pending**: `certificates: []` allowed; claim may be `CertificatePending`.
- **Certified**: at least one `TraceCertificate.v0`; semantic trace-hash alignment required.

## Rejection paths

- Checker returns `Rejected` on `TraceCertificate.v0`.
- Verifier records `failed` checks on `VerificationResult.v0`.
- Invalid schema or semantic mismatch: reject at validation (no artifact promotion).
