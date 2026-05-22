# Invalid fixture: failed_scientific_memory_import

Copy of the canonical [labtrust-release](../labtrust-release/) chain with one intentional violation for negative testing.

| Expected failure code | scientific_memory_import_failed |
|-----------------------|----------|

`ash
pcs validate-release-chain examples/labtrust-release-invalid/failed_scientific_memory_import/
`

Must fail with scientific_memory_import_failed.

Index: [../README.md](../README.md). Validator reference: [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
