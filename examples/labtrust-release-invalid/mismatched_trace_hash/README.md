# Invalid fixture mismatched_trace_hash

This directory copies the canonical [labtrust-release](../labtrust-release/) chain with one intentional violation for negative testing, and validation must fail with `trace_hash_mismatch`.

```bash
pcs validate-release-chain examples/labtrust-release-invalid/mismatched_trace_hash/
```

The index is [../README.md](../README.md), and validator reference is [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
