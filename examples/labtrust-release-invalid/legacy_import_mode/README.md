# Invalid fixture legacy_import_mode

This directory copies the canonical [labtrust-release](../labtrust-release/) chain with one intentional violation for negative testing, and validation must fail with `legacy_import_detected`.

```bash
pcs validate-release-chain examples/labtrust-release-invalid/legacy_import_mode/
```

The index is [../README.md](../README.md), and validator reference is [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
