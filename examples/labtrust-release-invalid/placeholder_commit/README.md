# Invalid fixture: placeholder_commit

Copy of the canonical [labtrust-release](../labtrust-release/) chain with one intentional violation for negative testing.

| Expected failure code | placeholder_commit_detected |
|-----------------------|----------|

`ash
pcs validate-release-chain examples/labtrust-release-invalid/placeholder_commit/
`

Must fail with placeholder_commit_detected.

Index: [../README.md](../README.md). Validator reference: [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
