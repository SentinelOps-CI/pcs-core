# PCS semantic check enforcement policy

ArtifactRegistry.v0 entries declare **semantic checks** as structured objects. Each check binds a `check_id` to a **severity**, **responsible_component**, and **execution policy** so downstream repos know who must run the rule, whether skipping is fatal, and how to report execution.

Machine-readable policy artifact: `examples/semantic_check_execution.valid.json` (`SemanticCheckExecution.v0`).

## Severities

| Severity | Meaning | Fatal if skipped (release mode) |
|----------|---------|----------------------------------|
| `required` | Must be implemented by the responsible component. | Yes |
| `optional` | Recommended; may be skipped. | No |
| `warning_only` | Advisory only. | No |
| `release_blocking` | Blocks `Validated` / `ProofChecked` release status. | Yes |
| `producer_responsible` | Runtime producer must execute before handoff. | Yes |
| `consumer_responsible` | Consumer executes at import/admission. | Yes |
| `validator_responsible` | Release validator must execute and cite in validation results. | Yes |

## Per-check execution fields (ArtifactRegistry.v0)

```json
{
  "check_id": "trace_hash_matches_runtime_receipt",
  "severity": "release_blocking",
  "responsible_component": "CertifyEdge",
  "execution_required_in_release_mode": true,
  "allowed_to_skip": false
}
```

| Field | Meaning |
|-------|---------|
| `execution_required_in_release_mode` | Must run when publishing or validating a release train. |
| `allowed_to_skip` | If `false`, skipping the check is a protocol violation. |

## Ownership vs production

| Field | Meaning |
|-------|---------|
| `schema_owner` | Authoritative schema owner (`pcs-core` for all v0 types). |
| `runtime_producer` | Authoritative default runtime emitter in the reference chain. |
| `producer` | **Deprecated** v0 compatibility alias; must equal `runtime_producer` on registry entries. |
| `allowed_runtime_producers` | Components permitted to emit instances at runtime. |

`HandoffManifest.v0` is schema-owned by **pcs-core** but may be produced at runtime by **LabTrust-Gym**, **CertifyEdge**, **Provability Fabric**, or **Scientific Memory**.

## Release-chain execution proof

`ReleaseChainValidationResult.v0` checks include `registry_check_refs` listing which registry semantic checks were executed:

```json
{
  "check_id": "trace_hash_alignment",
  "registry_check_refs": [
    "TraceCertificate.v0.trace_hash_matches_runtime_receipt",
    "RuntimeReceipt.v0.trace_hash_present"
  ],
  "status": "passed"
}
```

Downstream validators should emit the same `registry_check_refs` when they execute registry checks locally.

## Enforcement layers

| Layer | Meaning |
|-------|---------|
| `artifact_validate` | `pcs validate` / `pcs registry check-artifact` on one file. |
| `release_chain` | `pcs validate-release-chain` (30-check catalog). |
| `consumer` | Downstream import/admission. |
| `registry_metadata` | Validating `ArtifactRegistry.v0` itself. |

Catalog: `python/pcs_core/registry_semantics.py` (`CHECK_ENFORCEMENT`).

## Downstream reporting contract

When a component runs a registry semantic check, it should record:

1. `registry_ref` — `ArtifactType.check_id`
2. `status` — `passed` | `failed` | `skipped`
3. `responsible_component` — must match registry entry
4. `fatal` — `true` when `allowed_to_skip` is `false` and status is not `passed`

Attach these records to component validation reports or import into `ReleaseChainValidationResult.v0` via `registry_check_refs`.

## Reference commands

```bash
pcs registry validate examples/artifact_registry.valid.json
pcs registry audit
pcs validate examples/semantic_check_execution.valid.json
pcs conformance run --suite all
pcs conformance run --suite artifact-registry --json
pcs validate-release-chain examples/labtrust-release/
```
