# Invalid fixture: mismatched_trace_hash

Copy of the canonical [labtrust-release](../labtrust-release/) chain with one intentional violation for negative testing.

| Expected failure code | trace_hash_mismatch |
|-----------------------|----------|

`ash
pcs validate-release-chain examples/labtrust-release-invalid/mismatched_trace_hash/
`

Must fail with trace_hash_mismatch.

Index: [../README.md](../README.md). Validator reference: [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
