# Invalid fixture mismatched_certificate_id

This directory copies the canonical [labtrust-release](../labtrust-release/) chain with one intentional violation for negative testing, and validation must fail with `certificate_id_mismatch`.

```bash
pcs validate-release-chain examples/labtrust-release-invalid/mismatched_certificate_id/
```

The index is [../README.md](../README.md), and validator reference is [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
