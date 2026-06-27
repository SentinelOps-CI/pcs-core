"""PCS v0.1 LabTrust release-candidate pin (examples/labtrust-release/).

Downstream repos must copy fixtures from pcs-core at these values, not regenerate
partial fixtures independently. Regenerate only via the full atomic chain and
promote to examples/labtrust-release/.
"""

from __future__ import annotations

LABTRUST_RC_CERTIFICATE_ID = "cert-trace-a1b8ff9d-7d5f-489c-98b1-a3a630cb87d7"
LABTRUST_RC_TRACE_HASH = "sha256:c3e8a3dc4ad86d533de1dfa4ae7fe2a338c2cff3c945404c96a75216524d58cd"
LABTRUST_RC_CERTIFIED_BUNDLE_HASH = (
    "sha256:bb740698a01c4e918ca0f346e5bfaed83e6665da8df84e931c0d50e03ce82ffe"
)
LABTRUST_RC_LABTRUST_GYM_COMMIT = "17ed831acfd775889ab497d11004cceb083a9c2d"
LABTRUST_RC_CERTIFYEDGE_COMMIT = "635fca3771ad54fe3f8b49d1bb77ee35d0680ddc"
LABTRUST_RC_PROVABILITY_FABRIC_COMMIT = "b0dbbbe1c110ec2301d452d2ef1074354cce170f"
LABTRUST_RC_SCIENTIFIC_MEMORY_COMMIT = "0e059e934bc95bcc4dc0cb6593b18b07a28529a2"
LABTRUST_RC_PCS_CORE_COMMIT = "17e414501b3e1c58e8fbde1fe89a828440a945d9"
