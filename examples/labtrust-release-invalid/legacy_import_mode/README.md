# Invalid fixture: legacy_import_mode

Copy of the canonical [labtrust-release](../labtrust-release/) chain with one intentional violation for negative testing.

| Expected failure code | legacy_import_detected |
|-----------------------|----------|

`ash
pcs validate-release-chain examples/labtrust-release-invalid/legacy_import_mode/
`

Must fail with legacy_import_detected.

Index: [../README.md](../README.md). Validator reference: [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
