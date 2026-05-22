# Invalid fixture: mismatched_certified_bundle_hash

Copy of the canonical [labtrust-release](../labtrust-release/) chain with one intentional violation for negative testing.

| Expected failure code | verified_input_hash_mismatch |
|-----------------------|----------|

`ash
pcs validate-release-chain examples/labtrust-release-invalid/mismatched_certified_bundle_hash/
`

Must fail with verified_input_hash_mismatch.

Index: [../README.md](../README.md). Validator reference: [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
