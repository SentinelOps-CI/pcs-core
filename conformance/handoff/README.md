```bash
pcs validate examples/handoff_manifest.valid.json
pytest python/tests/test_protocol_conformance.py -k handoff
```

Handoff manifests must validate against `schemas/HandoffManifest.v0.schema.json`.
