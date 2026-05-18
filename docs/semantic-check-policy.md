# PCS semantic check enforcement policy

ArtifactRegistry.v0 entries declare **semantic checks** as structured objects. Each check binds a `check_id` to a **severity** and **responsible_component** so downstream repos know who must enforce the rule and whether a release may proceed.

## Severities

| Severity | Meaning |
|----------|---------|
| `required` | Must be implemented by the responsible component before claiming registry conformance. |
| `optional` | Recommended; failures are recorded but do not block release by default. |
| `warning_only` | Non-blocking; surfaced in validation reports only. |
| `release_blocking` | Failure prevents `Validated` / `ProofChecked` release status. |
| `consumer_responsible` | Enforced by the consuming repo at import/admission time, not at artifact emit time. |
| `producer_responsible` | Enforced by the runtime producer when the artifact is written. |

## Ownership vs production

| Field | Meaning |
|-------|---------|
| `schema_owner` | Repo that authors and versions the JSON Schema (`pcs-core` for all v0 types). |
| `runtime_producer` | Default component that emits instances in the reference LabTrust chain. |
| `allowed_runtime_producers` | Components permitted to emit instances of this type at runtime. |

`HandoffManifest.v0` is schema-owned by **pcs-core** but may be emitted by **LabTrust-Gym**, **CertifyEdge**, **Provability Fabric**, or **Scientific Memory** depending on the handoff stage.

## Release-chain linkage

`ReleaseChainValidationResult.v0` checks include `registry_check_refs` (for example `TraceCertificate.v0.trace_hash_matches_runtime_receipt`). Each ref must match `ArtifactType.check_id` in the registry.

## Enforcement layers (pcs-core v0.1)

| Layer | Meaning |
|-------|---------|
| `artifact_validate` | Enforced by `pcs validate` / `pcs registry check-artifact` semantics on a single file. |
| `release_chain` | Enforced by `pcs validate-release-chain` (30-check catalog). |
| `consumer` | Enforced by downstream import/admission (`consumer_responsible` / `producer_responsible`). |
| `registry_metadata` | Enforced when validating `ArtifactRegistry.v0` itself. |

Catalog mapping lives in `python/pcs_core/registry_semantics.py` (`CHECK_ENFORCEMENT`).

## Reference commands

```bash
pcs registry validate examples/artifact_registry.valid.json
pcs registry audit
pcs registry explain HandoffManifest.v0
pcs validate-release-chain examples/labtrust-release/
pcs conformance run --suite all
```
