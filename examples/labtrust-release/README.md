# LabTrust v0.1 release fixtures

This directory holds **generated end-to-end release evidence** for the PCS v0.1 LabTrust QC-release workflow. It is distinct from `examples/labtrust/`, which contains stable **schema conformance** fixtures.

## Regeneration

From the pcs-core repository root:

```bash
cd python
python -m pcs_core.release_fixtures --write
```

Set repository commit pins when generating from a real cross-repo pipeline:

```bash
export LABTRUST_GYM_COMMIT=<40-hex>
export CERTIFYEDGE_COMMIT=<40-hex>
export PROVABILITY_FABRIC_COMMIT=<40-hex>
export SCIENTIFIC_MEMORY_COMMIT=<40-hex>
python -m pcs_core.release_fixtures --write
```

`RELEASE_FIXTURE_MANIFEST.json` records `pcs_core_commit` from `git rev-parse HEAD` and the digests of every file in this directory.

## Validation

```bash
just validate-labtrust-release-fixtures
```

PCS artifacts in this directory must pass `pcs validate`. `trace.json` and `scientific_memory_import_report.json` are pipeline exports recorded in the manifest but are not PCS artifact schemas.

## Authority

Only this directory may be used as **PCS v0.1 release evidence**. See [docs/labtrust-v0.1-profile.md](../../docs/labtrust-v0.1-profile.md).
