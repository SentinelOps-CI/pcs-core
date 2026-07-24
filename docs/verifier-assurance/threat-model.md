# Verifier Assurance threat model (delta)

Extends [../security-governance.md](../security-governance.md) and [../pf-core/threat-model.md](../pf-core/threat-model.md).

| Threat | Mitigation |
|--------|------------|
| Forged accept after timeout | Fail-closed decision rule; fixture `invalid/timeout_accept/` |
| Silent float corruption of rates/rewards | Decimal strings + Canonical JSON float prohibition |
| Profile config drift without identity change | Material digests; config substitution tests |
| Private adjudication leak | Public records store commitment + location class only; content forbidden |
| Report denominator invention | Fail closed when cohort/adjudication inputs missing |
| Dialect shortcuts from producers | `benchmarks/verifier_assurance_conformance/` + suite gate |
| Schema fork / silent producer extension | Registry + `additionalProperties: false`; downstream sync notes |

pcs-core does not execute environments, train models (including RL), run attacks, or store private partner rationale text. See [non-claims.md](non-claims.md).
