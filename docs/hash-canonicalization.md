# Hash canonicalization

PCS artifacts bind integrity through digests (`signature_or_digest` in v0;
`artifact_digest` in v1) and cross-artifact hash links such as `trace_hash`.
Every repository must use the same canonical JSON algorithm so digests match
across language bindings.

## Algorithm version

The current algorithm is **PCS Canonical JSON v1** (`canonicalization_version: "v1"`).

Full RFC 8785 JCS was evaluated and deferred: adopting byte-identical JCS number
serialization would invalidate the existing cross-language digest corpus. v1 keeps
the established sorted-key compact UTF-8 algorithm and adds an explicit version id
plus a strict number policy for new integrity envelopes.

| Rule | Behavior |
|------|----------|
| Integrity fields stripped | Top-level `signature_or_digest`, `artifact_digest`, and `signature` |
| Object keys | Lexicographically sorted (UTF-8 code points via language JSON key sort) |
| Arrays | Order preserved (semantically significant) |
| Serialization | Compact JSON (`","` / `":"` separators), UTF-8, `ensure_ascii=False` / unescaped non-ASCII |
| Digest | SHA-256 over UTF-8 bytes, encoded as `sha256:` + 64 lowercase hex digits |
| Floats (release policy) | Prohibited (`float_prohibited`); store normalized decimal strings instead |
| Negative zero (release policy) | Prohibited (`negative_zero`) |
| Integers (release policy) | Must lie in `[-9007199254740991, 9007199254740991]` (`integer_out_of_range`) |

## APIs

Cross-language bindings expose two explicit entry points:

| API | Number policy | Use |
|-----|---------------|-----|
| `canonical_hash_legacy` / `canonicalHashLegacy` | Off | Phase 0 vectors and digests-compatible hashing |
| `canonical_hash_release` / `canonicalHashRelease` | Always on | Release integrity envelopes |

`canonical_hash` / `canonicalHash` remains an alias of the legacy path (optional
`enforce_number_policy` / `enforceNumberPolicy` flag in Python and TypeScript).

Release hashing must either return the same digest as every other language or raise
the same normalized rejection code:

- `float_prohibited`
- `integer_out_of_range`
- `negative_zero`

Legacy hashing remains digests-compatible with Phase 0 vectors. Note that ECMAScript
`JSON.stringify` collapses IEEE negative zero to `0`, so legacy digests for float
`-0` inputs may differ on TypeScript while release mode still rejects with
`negative_zero`.

v0 artifacts may omit `canonicalization_version`; consumers treat them as Canonical
JSON v1. New signed/hashed envelopes should set `"canonicalization_version": "v1"`.

## Domain-separated signatures (v1)

Cryptographic signatures cover:

```text
PCS:<artifact_type>:<schema_version>:<artifact_digest>
```

See [trust-model.md](trust-model.md) for key rotation and revocation.

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
| `test_vectors/hash/canonical_json_v1/` | Edge-case vectors (Unicode, escapes, ordering, integers, release rejects) |

Each accept case directory contains `input.json`, `canonical.txt`, and `digest.txt`.
Release reject cases add `expected_rejection.txt` and `legacy_digest.txt`.

Regenerate vectors after an intentional algorithm change.

```bash
cd python && python -m pcs_core.hash_vectors --write
pcs shared-hash-vectors write
```

## Downstream usage

Compute digests with `pcs hash` or the official language bindings, compare release
manifests using the same rules, and keep canonicalization logic in the shared
bindings instead of forking it inside application code.

See [downstream-schema-sync.md](downstream-schema-sync.md).
