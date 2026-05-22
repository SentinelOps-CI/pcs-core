# Hash canonicalization

PCS artifacts bind integrity through `signature_or_digest` and cross-artifact hash links such as `trace_hash` and `events_hash`, and every repository must use the same canonical JSON algorithm so digests match across bindings.

## Algorithm

The canonical algorithm parses the artifact as a JSON object, removes the top-level `signature_or_digest` field because the digest covers unsigned content, recursively sorts object keys lexicographically in UTF-8 while preserving array order, serializes compact JSON with insignificant whitespace removed, using UTF-8 with unescaped non-ASCII characters, applies SHA-256 to the UTF-8 bytes, and encodes the result as `sha256:` followed by 64 lowercase hexadecimal digits.

The same input yields the same digest in every language binding on every run.

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
| `test_vectors/hash/` | Cross-language parity across Python, Rust, and TypeScript |

Each per-artifact directory contains `input.json`, `canonical.txt`, and `digest.txt`.

Regenerate vectors after an intentional algorithm change.

```bash
cd python && python -m pcs_core.hash_vectors --write
pcs shared-hash-vectors write
```

## Downstream usage

Compute digests with `pcs hash` or the official language bindings, compare release manifests using the same rules, and keep canonicalization logic in the shared bindings instead of forking it inside application code.

See [downstream-schema-sync.md](downstream-schema-sync.md).
