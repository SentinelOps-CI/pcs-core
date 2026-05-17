# Hash Canonicalization

PCS artifacts bind integrity through `signature_or_digest` fields and cross-artifact hash links (`trace_hash`, `events_hash`, etc.). All repos must use the same canonical JSON hashing algorithm.

## Algorithm

1. Parse the artifact as a JSON object.
2. Remove `signature_or_digest` from the top-level object (the digest is over unsigned content).
3. Recursively sort object keys lexicographically (UTF-8 byte order). Array order is preserved.
4. Serialize with compact JSON: no insignificant whitespace, UTF-8, non-ASCII unescaped (`ensure_ascii=False` in Python).
5. Compute SHA-256 of the UTF-8 bytes.
6. Encode as `sha256:<lowercase hex>` (64 hex digits).

The same input must produce the same digest on every run and in every language binding.

## Test vectors

Frozen vectors live under `python/tests/hash_vectors/`:

| Artifact | Directory |
|----------|-----------|
| RuntimeReceipt.v0 | `python/tests/hash_vectors/RuntimeReceipt.v0/` |
| TraceCertificate.v0 | `python/tests/hash_vectors/TraceCertificate.v0/` |
| ScienceClaimBundle.v0 | `python/tests/hash_vectors/ScienceClaimBundle.v0/` |
| SignedScienceClaimBundle.v0 | `python/tests/hash_vectors/SignedScienceClaimBundle.v0/` |

Each directory contains:

- `input.json` — artifact JSON (may include `signature_or_digest`; it is stripped before hashing)
- `canonical.txt` — expected compact canonical JSON string
- `digest.txt` — expected `sha256:…` digest

Regenerate vectors after intentional algorithm changes:

```bash
cd python && python -m pcs_core.hash_vectors --write
```

## Downstream usage

```bash
pcs hash path/to/artifact.json
```

Python: `from pcs_core.hash import canonical_hash, canonical_json_bytes`

Rust: `pcs_core::canonical_hash`

TypeScript: `canonicalHash` from `@pcs/core`
