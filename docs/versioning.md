# Versioning and Canonical Hash

## Schema version

v0.1 artifacts use `"schema_version": "v0"`. Breaking changes require a new schema file (e.g. `ClaimArtifact.v1.schema.json`), not silent edits to v0 files.

## Canonical hash algorithm

Used by `pcs hash` and binding logic across repos:

1. Parse JSON to a value tree.
2. Remove `signature_or_digest` if present (hash is over content excluding self-signature).
3. Recursively sort object keys lexicographically (UTF-8 byte order).
4. Serialize with compact JSON: no insignificant whitespace, UTF-8, `ensure_ascii=False` equivalent.
5. Compute SHA-256 of the UTF-8 bytes.
6. Encode as `sha256:<lowercase hex>`.

The same input file hashed twice must yield identical digests.

## Arrays

Array order is preserved. Only object keys are sorted.

## Floating point

v0.1 examples use integers and strings only. If floats appear, producers should normalize (e.g. fixed decimal strings) before hashing.

## Pinning for downstream repos

Pin pcs-core by git tag or submodule commit. Import schemas from `schemas/`; do not fork field names locally.
