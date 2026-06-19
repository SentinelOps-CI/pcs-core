"""Parity gate: PCS hash vectors must match provability-fabric-core adapter fixtures."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify-pf-core-hash-vectors.sh"
LOCAL_VECTORS = Path(__file__).resolve().parent / "hash_vectors"
PF_CORE_TAG = os.environ.get("PF_CORE_TAG", "pf-core-v0.6.0")


@pytest.mark.skipif(not SCRIPT.is_file(), reason="verify script missing")
def test_hash_vectors_match_pf_core_adapter() -> None:
    """Frozen vectors under python/tests/hash_vectors match pf-core tag."""
    env = {**os.environ, "PF_CORE_TAG": PF_CORE_TAG}
    proc = subprocess.run(
        ["bash", str(SCRIPT), str(LOCAL_VECTORS)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_trace_certificate_vector_has_sha256_prefix_digest() -> None:
    digest = (LOCAL_VECTORS / "TraceCertificate.v0" / "digest.txt").read_text(
        encoding="utf-8"
    ).strip()
    assert digest.startswith("sha256:"), "PCS digest must retain sha256: prefix form"
