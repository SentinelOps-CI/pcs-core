# CertifyEdge mock fixture

Pre-generated `CertificateChecked` certificate using `PF_CORE_CERTIFYEDGE_MODE=mock`.
No live CertifyEdge CLI is required to validate this fixture.

## Regenerate

```bash
export PF_CORE_CERTIFYEDGE_MODE=mock
pcs pf-core certifyedge-check \
  --trace examples/pf-core-valid/certifyedge_mock/trace.json \
  --property qc_release.temporal.safety \
  --out examples/pf-core-valid/certifyedge_mock/certificate.json
```

## Verify

```bash
pcs pf-core validate-trace examples/pf-core-valid/certifyedge_mock/trace.json
pcs examples check examples/pf-core-valid/certifyedge_mock
```

See `docs/pf-core/certifyedge.md` for the env contract and release-gate dry-run notes.
