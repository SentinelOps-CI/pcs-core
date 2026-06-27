# Invalid fixture failed_scientific_memory_import

This directory copies the canonical [labtrust-release](../labtrust-release/) chain with one intentional violation for negative testing, and validation must fail with `scientific_memory_import_failed`.

```bash
pcs validate-release-chain examples/labtrust-release-invalid/failed_scientific_memory_import/
```

The index is [../README.md](../README.md), and validator reference is [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
