# PCS Examples

Valid examples live in `examples/`:

| File | Artifact |
|------|----------|
| `assumption_set.valid.json` | AssumptionSet.v0 |
| `source_span.valid.json` | SourceSpan.v0 |
| `claim_artifact.valid.json` | ClaimArtifact.v0 |
| `runtime_receipt.valid.json` | RuntimeReceipt.v0 |
| `trace_certificate.valid.json` | TraceCertificate.v0 |
| `evidence_bundle.valid.json` | EvidenceBundle.v0 |
| `science_claim_bundle.valid.json` | ScienceClaimBundle.v0 |
| `verification_result.valid.json` | VerificationResult.v0 |

Invalid examples (must fail validation):

| File | Failure |
|------|---------|
| `invalid_unknown_status.json` | Unknown status enum |
| `invalid_missing_assumption_set.json` | Missing `assumption_set_ref` on claim |
| `invalid_mismatched_trace_hash.json` | Receipt vs certificate `trace_hash` mismatch |

## Commands

```bash
just validate-examples
pcs validate examples/science_claim_bundle.valid.json
pcs examples check
```
