# JSON Schema format assertions

PCS Draft 2020-12 schemas declare `"format"` keywords. In Python, `Draft202012Validator`
is constructed with `jsonschema.FormatChecker` so those formats are **assertions**, not
annotations.

## Asserted formats

| Format | Normative today | Typical fields |
|--------|-----------------|----------------|
| `date-time` | Yes | `created_at`, `generated_at`, `signed_at` |
| `uri` | Yes | `source_repo`, producer `repo` pins |
| `uuid` | Vocabulary ready | `common.defs.json#/$defs/uuid` (use when introducing UUID fields) |
| `duration` | Vocabulary ready | `common.defs.json#/$defs/duration` (ISO 8601 durations) |
| `hostname` | Vocabulary ready | `common.defs.json#/$defs/hostname` |
| `email` | Vocabulary ready | `common.defs.json#/$defs/email` |

Formats **not** listed in `ASSERTED_FORMATS` (`python/pcs_core/validate_detect.py`) are ignored
by the Python checker even if a schema mentions them.

TypeScript already enables `ajv-formats`. Rust schema validation should treat the same
formats as assertions when format support is available in the `jsonschema` crate options.

## Negative fixtures

Invalid format examples live under `examples/invalid-format/`:

| Case | Expected failure |
|------|------------------|
| `malformed_uri.json` | `uri` |
| `malformed_date_time.json` | `date-time` |
| `invalid_uuid.json` | `uuid` |
| `invalid_duration.json` | `duration` |
| `invalid_hostname.json` | `hostname` |
| `invalid_email.json` | `email` |

Run:

```bash
cd python && pytest tests/test_phase1_protocol_hardening.py -q
```
