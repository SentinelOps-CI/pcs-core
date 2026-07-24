# Verifier Assurance — non-claims

## PCS does not claim

- Verifier implementation correctness beyond recorded checks and digests.
- Campaign safety, ethics, or exhaustive coverage.
- That adjudication labels are ground truth.
- That `observational` / `runtime_observed` evidence is formally verified.
- That pcs-core executes environments, trains models (including RL loops), runs attacks, or stores private adjudication rationale text.
- That optional `invocation_ref` digests prove a portable invocation record schema exists in PCS (they are opaque producer pins only).

## PCS does claim (bounded)

- Schema validity and Canonical JSON digests for published VA artifacts.
- Deterministic offline semantic validation against declared rules.
- Deterministic rebuild of `VerifierAssuranceReport.v1` bodies from the same local inputs (excluding integrity fields).

See [ownership.md](ownership.md) and [threat-model.md](threat-model.md).
