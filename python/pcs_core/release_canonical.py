"""PCS v0.1 LabTrust release-candidate pin (examples/labtrust-release/).

Downstream repos must copy fixtures from pcs-core at these values, not regenerate
partial fixtures independently. Regenerate only via the full atomic chain and
promote to examples/labtrust-release/.
"""

from __future__ import annotations

LABTRUST_RC_CERTIFICATE_ID = "cert-trace-886c95f0-5d63-42d6-aa13-5891c12c5a6a"
LABTRUST_RC_TRACE_HASH = "sha256:c3e8a3dc4ad86d533de1dfa4ae7fe2a338c2cff3c945404c96a75216524d58cd"
LABTRUST_RC_CERTIFIED_BUNDLE_HASH = (
    "sha256:30b5b731a298922c41432de82c4ea407ec732f1e54f85b45ed9344ee5ec2c536"
)
LABTRUST_RC_LABTRUST_GYM_COMMIT = "4c5439ae358733f9a4c4a58e33fdaed1ab0d29de"
LABTRUST_RC_CERTIFYEDGE_COMMIT = "cb6848001e2e60a484e04eba5ad6be3fe2e4eccc"
LABTRUST_RC_PROVABILITY_FABRIC_COMMIT = "0f659b90c80c46a6bbfd51b0d37ea723b032fb9d"
LABTRUST_RC_SCIENTIFIC_MEMORY_COMMIT = "c4259a4cb79fe7b195fd156feb346c08fc334d33"
