# Invalid LabTrust release-chain fixtures

Each subdirectory is a copy of the canonical [`../labtrust-release/`](../labtrust-release/) chain with **one intentional violation**. `pcs validate-release-chain` must fail with the listed code.

| Directory | Expected failure code |
|-----------|------------------------|
| `placeholder_commit/` | `placeholder_commit_detected` |
| `mismatched_certificate_id/` | `certificate_id_mismatch` |
| `mismatched_trace_hash/` | `trace_hash_mismatch` |
| `mismatched_certified_bundle_hash/` | `verified_input_hash_mismatch` |
| `failed_scientific_memory_import/` | `scientific_memory_import_failed` |
| `legacy_import_mode/` | `legacy_import_detected` |

Regenerate from canonical:

```bash
python python/scripts/materialize_invalid_release_fixtures.py
```

Validator reference: [docs/labtrust-release-fixtures.md](../../docs/labtrust-release-fixtures.md).
