```bash
pcs conformance run --suite hash
pcs shared-hash-vectors verify
cd rust && cargo test -p pcs-core hash_vectors
cd typescript/packages/core && npm test -- --test-name-pattern=hash
```
