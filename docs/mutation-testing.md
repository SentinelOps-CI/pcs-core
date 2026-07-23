# Mutation testing (deferred scaffold)
#
# Goal: mutmut (or cosmic-ray) against release/certificate validators:
#   python/pcs_core/validate*.py
#   python/pcs_core/external_attestation.py
#   python/pcs_core/pf_core_bundle.py
#   python/pcs_core/release_chain.py
#
# Why deferred:
# - Full mutation runs are long and flaky on Windows CI without dedicated runners.
# - Org CI minutes / caching for mutant corpora are not provisioned yet.
#
# Local enablement (when ready):
#   pip install mutmut
#   cd python
#   mutmut run --paths-to-mutate pcs_core/external_attestation.py,pcs_core/pf_core_bundle.py
#   mutmut results
#
# Acceptance bar (future): surviving mutants on digest/path/attestation gates = 0.
# Until then, Hypothesis property tests + adversarial fixtures cover the critical paths.
