# PCS status transition policy (v0.1)

Status transitions are enforced by `pcs check-status-transition` and implemented in `python/pcs_core/status_policy.py`.

## Allowed transitions

| From | To |
|------|-----|
| `Draft` | `RuntimeObserved` |
| `RuntimeObserved` | `CertificatePending`, `CertificateChecked` |
| `CertificatePending` | `CertificateChecked`, `Rejected` |
| `CertificateChecked` | `ProofChecked` |
| `ProofChecked` | `Stale` |

## Terminal statuses

`Rejected`, `Stale`, and `Deprecated` remain terminal until maintainers apply regeneration, refresh, or migration respectively.

## Forbidden transitions

| From | To | Reason |
|------|-----|--------|
| `Rejected` | `ProofChecked` | Regenerate artifacts |
| `Stale` | `ProofChecked` | Refresh evidence |
| `Deprecated` | `ProofChecked` | Migrate schema |
| `Draft` | `ProofChecked` | Skip runtime and certificate stages |
| `RuntimeObserved` | `ProofChecked` | Skip certificate attachment |

## CLI

```bash
pcs explain-status ProofChecked
pcs status check-transition old.json new.json
pcs check-status-transition old.json new.json
```

Each file must include a top-level `status` field (for example `trace_certificate.json`, `verification_result.json`).
