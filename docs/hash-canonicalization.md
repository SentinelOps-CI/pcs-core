# Hash canonicalization

PCS artifacts bind integrity through `signature_or_digest` and cross-artifact hash links (`trace_hash`, `events_hash`, and related fields). All repositories must use the same canonical JSON algorithm.

## Algorithm

1. Parse the artifact as a JSON object.
2. Remove top-level `signature_or_digest` (the digest covers unsigned content).
3. Recursively sort object keys lexicographically (UTF-8). Array order is preserved.
4. Serialize as compact JSON: no insignificant whitespace, UTF-8, non-ASCII unescaped.
5. SHA-256 the UTF-8 bytes.
6. Encode as `sha256:<lowercase hex>` (64 hex digits).

The same input must yield the same digest in every language binding and on every run.

## Verify

```bash
pcs hash path/to/artifact.json
python -m pcs_core.hash_vectors --verify          # per-language vectors
pcs shared-hash-vectors verify                    # test_vectors/hash/
```

## Test vectors

| Location | Scope |
|----------|--------|
| `python/tests/hash_vectors/` | Per-artifact canonical JSON and digests |
| `test_vectors/hash/` | Cross-language parity (Python, Rust, TypeScript) |

Each per-artifact directory contains `input.json`, `canonical.txt`, and `digest.txt`.

Regenerate after an intentional algorithm change:

```bash
cd python && python -m pcs_core.hash_vectors --write
pcs shared-hash-vectors write
```

## Downstream usage

- Compute digests with `pcs hash` or official bindings.
- Compare release manifests using the same rules.
- Do not fork canonicalization in application code.

See [downstream-schema-sync.md](downstream-schema-sync.md).
