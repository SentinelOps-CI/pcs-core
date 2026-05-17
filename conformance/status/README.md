```bash
pcs check-status-transition Rejected ProofChecked
pytest python/tests/test_protocol_conformance.py -k status_transition
```

Forbidden transitions are enforced by `python/pcs_core/status_policy.py`.
