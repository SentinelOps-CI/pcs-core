# Invalid fixture: mismatched_certificate_id

Copy of the canonical [labtrust-release](../labtrust-release/) chain with one intentional violation for negative testing.

| Expected failure code | certificate_id_mismatch |
|-----------------------|----------|

`ash
pcs validate-release-chain examples/labtrust-release-invalid/mismatched_certificate_id/
`

Must fail with certificate_id_mismatch.

Index: [../README.md](../README.md). Validator reference: [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
