# Rust fuzz targets (Phase 7)

pcs-core CI runs `cargo test` and `proptest` property tests on every PR.

Full libfuzzer / cargo-fuzz targets for JSON, paths, hashes, and manifests are
scaffolded but deferred until runners install `cargo-fuzz` and nightly fuzz
toolchains:

```bash
cargo install cargo-fuzz
cd rust
# future: cargo fuzz run json_artifact -- -max_total_time=60
```

Until then, prefer:
- `cargo test --locked` (includes proptest cases once added)
- Python Hypothesis path/attestation properties
- TypeScript `fast-check` properties
