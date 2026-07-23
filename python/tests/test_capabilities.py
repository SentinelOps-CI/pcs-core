"""Tests for pcs capabilities reporting."""

from __future__ import annotations

import json
import subprocess
import sys

from pcs_core.capabilities import (
    CAPABILITY_KEYS,
    detect_capabilities,
    format_capabilities_report,
)


def test_detect_capabilities_shape() -> None:
    report = detect_capabilities()
    assert report["product"] in {"validator", "verifier"}
    caps = report["capabilities"]
    assert set(CAPABILITY_KEYS) <= set(caps)
    for key in CAPABILITY_KEYS:
        assert isinstance(caps[key], bool)
    assert caps["schema_validation"] is True
    text = format_capabilities_report(report)
    assert "schema validation available:" in text
    assert "live CertifyEdge available:" in text


def test_capabilities_cli_text_and_json() -> None:
    text = subprocess.run(
        [sys.executable, "-m", "pcs_core.cli", "capabilities"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "schema validation available: yes" in text.stdout
    assert "Lean toolchain available:" in text.stdout

    raw = subprocess.run(
        [sys.executable, "-m", "pcs_core.cli", "capabilities", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(raw.stdout)
    assert payload["capabilities"]["schema_validation"] is True
    assert "live_certifyedge" in payload["capabilities"]


def test_validator_product_does_not_claim_lean_without_toolchain(
    monkeypatch,
) -> None:
    import pcs_core.capabilities as caps

    monkeypatch.setattr(caps, "_lake_available", lambda: False)
    report = caps.detect_capabilities()
    assert report["capabilities"]["lean_toolchain"] is False
    assert report["capabilities"]["pf_core_kernel"] is False
    assert report["capabilities"]["pcs_envelope_kernel"] is False
    assert report["product"] == "validator"
    joined = " ".join(report["notes"]).lower()
    assert "lean" in joined
