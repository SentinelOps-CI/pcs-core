```bash
pcs registry validate examples/artifact_registry.valid.json
pcs registry check-artifact examples/labtrust-release/trace_certificate.json
pytest python/tests/test_protocol_conformance.py -k registry
```

Registry entries drive producer, status, and release-field admission checks.
