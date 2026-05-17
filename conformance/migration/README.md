```bash
pcs migrate --from v0 --to v0 examples/runtime_receipt.valid.json
pytest python/tests/test_protocol_conformance.py -k migration
```

Migration reports must validate against `schemas/MigrationReport.v0.schema.json`.
