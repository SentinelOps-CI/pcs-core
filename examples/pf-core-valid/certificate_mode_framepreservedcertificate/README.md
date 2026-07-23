# Valid FramePreservedCertificate fixture

Valid PF-Core trace exercising **`FramePreservedCertificate`** transition witnesses.

Obligations prove `stepState pre event = some post` for the allow event, deny identity
for the deny event, `frameValidD` at every post-state, and resource / active-principal /
tenant / capability-frame update equalities. Codegen does not use `applyEvent` fallbacks.

Public issuance remains disabled; use `--allow-non-public-modes` for lean-check.
