# pcs-core

**Proof-Carrying Science (PCS)** — canonical protocol repository for artifact schemas, status enums, validation, hash canonicalization, and language bindings.

pcs-core is boring, stable, and dependency-like. LabTrust-Gym, CertifyEdge, provability-fabric, and scientific-memory consume it; they must not fork artifact shapes.

## v0.1 artifacts

AssumptionSet, SourceSpan, ClaimArtifact, RuntimeReceipt, TraceCertificate, EvidenceBundle, ScienceClaimBundle, VerificationResult — see [`schemas/`](schemas/) and [`docs/protocol.md`](docs/protocol.md).

## Quick start

```bash
# Python CLI
cd python && pip install -e ".[dev]"
pcs validate ../examples/science_claim_bundle.valid.json
pcs hash ../examples/science_claim_bundle.valid.json

# All checks
just ci
```

## CLI

| Command | Description |
|---------|-------------|
| `pcs validate <file>` | Schema + semantic validation |
| `pcs hash <file>` | Canonical SHA-256 digest |
| `pcs status <file>` | Print artifact status field(s) |
| `pcs schema check` | Validate JSON schemas |
| `pcs examples check` | Validate all `examples/*.valid.json` |

## Layout

```
schemas/     JSON Schema (Draft 2020-12)
examples/    Valid and invalid fixtures
docs/        Protocol, trust model, lifecycle
python/      Python package + `pcs` CLI
rust/        Rust crate
typescript/  TypeScript package
lean/        Minimal Lean structures
```

## Downstream integration

1. **Validate**: `pcs validate` or import `pcs_core` / `pcs-core` / `@pcs/core`.
2. **Hash**: use `pcs hash` algorithm ([docs/versioning.md](docs/versioning.md)).
3. **Schemas**: vendor or submodule `schemas/`; pin releases.
4. **Status**: import canonical enum only.
5. **New types**: add `*.v1` schemas; do not break v0.

## License

Apache-2.0 — see [LICENSE](LICENSE).
