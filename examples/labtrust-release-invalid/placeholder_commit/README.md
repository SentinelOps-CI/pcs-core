# Invalid fixture placeholder_commit

This directory copies the canonical [labtrust-release](../labtrust-release/) chain with one intentional violation for negative testing, and validation must fail with `placeholder_commit_detected`.

```bash
pcs validate-release-chain examples/labtrust-release-invalid/placeholder_commit/
```

The index is [../README.md](../README.md), and validator reference is [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
