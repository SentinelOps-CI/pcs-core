# PF-Core trace ↔ PCS trace_certificate mapping

Phase 7 documents how PCS release artifacts relate to PF-Core traces and certificates. PCS and PF-Core use **different certificate schemas**; this document records field correspondence and shared hash rules. It does not unify schemas.

**Reference implementation:** [provability-fabric-core](https://github.com/SentinelOps-CI/provability-fabric-core) tag `pf-core-v0.6.0`, adapter `adapters/pcs/normalize_release.py`.

**PF-Core hash and certificate semantics:** [certificate-semantics.md](https://github.com/SentinelOps-CI/provability-fabric-core/blob/pf-core-v0.6.0/pf-core/docs/certificate-semantics.md) (hash chain section).

---

## PCS `trace_certificate` (v0) vs PF-Core artifacts

| PCS `trace_certificate` field | PF-Core equivalent | Notes |
|------------------------------|-------------------|-------|
| `certificate_id` | `certificate.certificate_id` | PCS uses `cert-*` naming; PF-Core generates `cert-{uuid}` |
| `schema_version` | `certificate.schema_version` | PCS `v0` vs PF-Core `pf-core.certificate.v0` |
| `trace_hash` | `trace.trace_hash`, `certificate.trace_hash` | PCS uses `sha256:` prefix; PF-Core stores hex64 — normalize at boundary |
| `spec_hash` | `certificate.contract_hash` | PCS spec hash binds to PF-Core contract hash |
| `property_id` | (none) | PCS property identifier; map to `policy_ref` or contract id when bridging |
| `checker` | `certificate.checker` | PCS `certifyedge` vs PF-Core `lean4` |
| `checker_version` | `certificate.checker_version` | Version strings differ by design |
| `status` | `certificate.safe` | `CertificateChecked` + `safe: true` documented equivalence |
| `counterexample_ref` | (none) | PCS-only; out of PF-Core scope |
| `created_at` | (none) | Organizational metadata |
| `producer` / `producer_version` | `certificate.created_by` | Optional PF-Core field |
| `source_repo` / `source_commit` | `certificate.proof_ref` | Different semantics; cross-reference only |
| `signature_or_digest` | (none) | PCS bundle integrity; post-incident-proofs layer |

---

## Event / trace hash rules (shared)

Both repos agree on:

1. **Genesis** `previous_event_hash`: 64 ASCII `0` characters.
2. **Canonical JSON:** sorted keys, minimal separators (`separators=(",", ":")`).
3. **`event_hash`:** `sha256(payload)` as lowercase hex; accept `sha256:` prefix at validation.
4. **`trace_hash`:** `sha256(canonical_json(trace \ {trace_hash}))`.

PCS hash vectors under `python/tests/hash_vectors/` must match provability-fabric-core `adapters/pcs/tests/fixtures/hash_vectors/` at the pinned PF-Core tag.

---

## LabTrust replay path

Pinned LabTrust release fixtures (e.g. `examples/labtrust/trace_certificate.valid.json`) feed PF-Core traces via the untrusted adapter:

```
labtrust-release/trace_certificate.valid.json
  → normalize_release.normalize_labtrust_release()
  → pf-core/examples/valid/pcs_replay_trace.json
```

### Release directory fields

| LabTrust / PCS artifact | Role in PF-Core trace |
|-------------------------|----------------------|
| `trace_certificate.valid.json` | Source `trace_hash` / `spec_hash` for mapping docs; adapter reads when present |
| Release observation (when emitted) | Compiles to `pf-core.event.v1` via `compile-observation` |
| PCS `trace_hash` (with `sha256:` prefix) | Normalizes to hex64 for `trace.trace_hash` binding |
| PCS `spec_hash` | Maps to `certificate.contract_hash` when emitting PF-Core certificate |

The reference adapter builds a single-event trace with `lab.release` effect, principal `lab-operator-1`, and genesis hash chain. See `pcs_replay_trace.json` in provability-fabric-core.

### Verification command

```bash
PYTHONPATH=pf-core/validator python -m pf_core.cli core check-trace \
  --schemas pf-core/schemas \
  --file pf-core/examples/valid/pcs_replay_trace.json
```

---

## Assurance boundary

| Layer | Claim |
|-------|-------|
| PF-Core `safe: true` | T1 (Lean-proved) + T4 (runtime deciders) |
| PCS `CertificateChecked` | PCS checker semantics |
| This mapping doc | Organizational cross-reference only |

PCS does not expand PF-Core TCB. Policy alignment remains vector-tested in provability-fabric-core.
