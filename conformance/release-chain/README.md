Run from repo root after `pip install -e python/.[dev]`:

```bash
pcs validate-release-chain examples/labtrust-release/
pcs validate-release-chain examples/labtrust-release/ --json
pcs validate-release-chain examples/labtrust-release/ --out examples/labtrust-release/release_chain_validation_result.v0.json
```
