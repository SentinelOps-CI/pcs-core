"""Parity gate: PCS hash vectors must match provability-fabric-core adapter fixtures."""

from __future__ import annotations

import os
from pathlib import Path

from pcs_core.pf_core_hash_vector_parity import verify_pf_core_hash_vectors

ROOT = Path(__file__).resolve().parents[2]
LOCAL_VECTORS = Path(__file__).resolve().parent / "hash_vectors"
PF_CORE_TAG = os.environ.get("PF_CORE_TAG", "pf-core-v0.6.0")
UPSTREAM_FIXTURES = os.environ.get("PF_CORE_UPSTREAM_VECTORS")


def test_hash_vectors_match_pf_core_adapter_native() -> None:
    """Frozen vectors match pf-core tag via native parity checker (CI-friendly)."""
    upstream = Path(UPSTREAM_FIXTURES) if UPSTREAM_FIXTURES else None
    drift = verify_pf_core_hash_vectors(
        LOCAL_VECTORS,
        pf_core_tag=PF_CORE_TAG,
        upstream_dir=upstream,
    )
    assert drift == [], "\n".join(drift)


def test_trace_certificate_vector_has_sha256_prefix_digest() -> None:
    digest = (
        (LOCAL_VECTORS / "TraceCertificate.v0" / "digest.txt").read_text(encoding="utf-8").strip()
    )
    assert digest.startswith("sha256:"), "PCS digest must retain sha256: prefix form"
