# Tool-use safety release fixtures

Conformance and release fixtures for workflow `agent_tool_use.safety_v0` exercise the shared PCS trust loop with `ToolUseTrace.v0` and `ToolUseCertificate.v0`.

The workflow profile appears in `examples/workflow_profiles/agent_tool_use_safety.valid.json`, and the guide is [docs/workflow-profiles.md](../../docs/workflow-profiles.md).

## Validate

```bash
pcs validate examples/tool-use-release/tool_use_trace.valid.json
pcs validate examples/tool-use-release/tool_use_certificate.valid.json
pcs validate-release-chain examples/tool-use-release/
pcs conformance run --suite tool-use
pcs conformance run --suite multidomain
```

## Artifacts

| File | Type |
|------|------|
| `tool_use_trace.valid.json` | `ToolUseTrace.v0` |
| `tool_use_certificate.valid.json` | `ToolUseCertificate.v0` |
| `runtime_receipt.json` | `RuntimeReceipt.v0` |
| `handoff_manifest.*.v0.json` | `HandoffManifest.v0` |
| `science_claim_bundle.certified.json` | `ScienceClaimBundle.v0` |
| `verification_result.json` | `VerificationResult.v0` |
| `signed_science_claim_bundle.json` | `SignedScienceClaimBundle.v0` |
| `release_manifest.v0.json` | `ReleaseManifest.v0` |
| `release_chain_validation_result.v0.json` | `ReleaseChainValidationResult.v0` |
| `RELEASE_FIXTURE_MANIFEST.json` | Digest manifest for `pcs validate-release-chain` |

Invalid cases live under `examples/tool-use-release-invalid/`.

Regenerate through `python scripts/materialize_tool_use_fixtures.py` or `just materialize-protocol`.
