# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes |
| < 0.1   | No |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

1. Email **security@sentinelops.ci** (or open a private [GitHub Security Advisory](https://github.com/SentinelOps-CI/pcs-core/security/advisories/new) if you have access).
2. Include: affected revision/tag, component (schemas, Python validator, Lean kernel, CI, OCI image), reproduction steps, and impact.
3. Allow up to **5 business days** for an initial acknowledgement and **90 days** for coordinated disclosure unless we agree otherwise.

We will confirm receipt, triage severity, and coordinate a fix and advisory for confirmed issues.

## Security review requirements

The following changes **require** an explicit security-minded review (CODEOWNERS + at least one maintainer approval) before merge:

| Area | Paths |
|------|-------|
| Lean trust kernels | `lean/PFCore/**`, `lean/PCS/**`, `lean/lakefile.lean`, `lean/lean-toolchain` |
| Normative schemas | `schemas/**` |
| Hash / signing semantics | `python/pcs_core/hash.py`, `docs/hash-canonicalization.md`, `docs/trust-model.md` |
| Release-chain validation | `python/pcs_core/release_chain*.py`, `python/pcs_core/pf_core_bundle.py` |
| CI / supply chain | `.github/workflows/**`, `pins/**`, `docker/**` |

Reviewers must confirm:

- No weakening of claim classes or Lean discharge boundaries
- Schema changes are versioned and documented
- Pins (Actions SHAs, elan checksum, CertifyEdge digest) remain immutable where required
- Secrets are not introduced into fixtures or docs

## Signed release tags

Maintainers should create annotated, signed tags for releases:

```bash
git tag -s "v$(tr -d '\r\n' < VERSION)" -m "pcs-core $(tr -d '\r\n' < VERSION)"
git push origin "v$(tr -d '\r\n' < VERSION)"
```

Consumers should verify tag signatures against the published maintainer key list (document keys in the GitHub Release notes until a keyserver/SIGSTORE workflow is automated).

## Secret scanning

- Enable GitHub secret scanning and push protection for the repository (org admin setting).
- Optionally run [gitleaks](https://github.com/gitleaks/gitleaks) locally: `gitleaks detect --source .`
- Never commit CertifyEdge private keys, signing keys, or `.env` files.

## Further reading

- [docs/security-governance.md](docs/security-governance.md) — branch protection, required checks, SBOM/SLSA, retention
- [docs/distribution.md](docs/distribution.md) — validator vs verifier products
- [docs/pf-core/threat-model.md](docs/pf-core/threat-model.md) — PF-Core adversary model
