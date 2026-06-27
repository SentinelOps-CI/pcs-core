# PCS TraceCertificate to PFCoreCertificate bridge artifact

This document specifies the organizational bridge between PCS release-layer
`TraceCertificate.v0` artifacts and PF-Core `PFCoreCertificate.v0` claim objects.
It is a cross-reference spec for demos and adapters; it does not unify schemas.

## Purpose

PCS science bundles attach `TraceCertificate.v0` objects checked by external
tools (e.g. CertifyEdge). PF-Core certificates carry explicit `claim_class`
values that state what assurance was obtained. The bridge maps PCS checker output
into PF-Core certificate fields without expanding the PF-Core TCB.

## Field mapping

| PCS `TraceCertificate.v0` | PF-Core `PFCoreCertificate.v0` | Bridge rule |
|---------------------------|-------------------------------|-------------|
| `certificate_id` | `certificate_id` | Prefix optional; preserve id for cross-reference |
| `trace_hash` | `trace_hash` | Normalize `sha256:` prefix at boundary |
| `spec_hash` | `contract_hash` | Direct bind |
| `checker` | `checker` | Copy verbatim |
| `checker_version` | `checker_version` | Copy verbatim |
| `status: CertificateChecked` | `claim_class: CertificateChecked` | Required when external checker attests |
| `source_repo` | `source_repo` | Copy verbatim |
| `source_commit` | `source_commit` | Copy verbatim |
| `property_id` | (none) | Record in trace event `contract_refs` when compiling |
| `counterexample_ref` | (none) | PCS-only; PF-Core `OutOfScope` if replay needed |
| `signature_or_digest` | (none) | PCS bundle integrity; recompute PF-Core digest |

## Claim class selection

| Bridge operation | Required `claim_class` |
|------------------|------------------------|
| External checker attestation only | `CertificateChecked` |
| PF-Core runtime compiler + hash chain | `RuntimeChecked` |
| Deterministic hash replay | `ReplayValidated` |
| Lean kernel concrete proof | `LeanKernelChecked` |
| Deferred registry checks documented | `AssumptionDeclared` |

Do not emit `LeanKernelChecked` from the bridge when only PCS
`CertificateChecked` status is available.

## Bridge workflow (demo)

```
examples/labtrust/trace_certificate.valid.json
  → pf_core_labtrust_adapter.normalize_labtrust_release()
  → examples/pf-core-valid/labtrust_replay/trace.json
  → pcs pf-core replay-trace trace.json
  → pcs pf-core attach-certificate-check --trace trace.json ...
  → PFCoreCertificate.v0 (claim_class: CertificateChecked)
```

## Assurance boundary

| Layer | What the bridge claims |
|-------|------------------------|
| PCS `CertificateChecked` | External checker semantics for the declared property |
| PF-Core `CertificateChecked` | Same attestation recorded in PF-Core schema |
| PF-Core `ReplayValidated` | Hash chain reproducibility only |
| PF-Core `LeanKernelChecked` | Not implied by this bridge |

Adapters that perform the bridge are **untrusted**. All bridged artifacts must
pass PCS schema and PF-Core semantic validation before release.

## Related documents

- [claim-boundary.md](claim-boundary.md) — claim class definitions
- [pf-core-trace-mapping.md](../pf-core-trace-mapping.md) — trace field mapping
- [assumptions.md](assumptions.md) — deferred registry obligations
