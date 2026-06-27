#!/usr/bin/env python3
"""Build examples/labtrust-release-invalid/* from the canonical RC chain."""

from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "examples" / "labtrust-release"
INVALID_ROOT = ROOT / "examples" / "labtrust-release-invalid"

sys.path.insert(0, str(ROOT / "python"))

from pcs_core.release_fixtures import MANIFEST_ARTIFACTS, MANIFEST_NAME, file_digest  # noqa: E402


def _write_manifest(target: Path, manifest: dict) -> None:
    artifacts = {
        name: file_digest((target / name).read_bytes()) for name in MANIFEST_ARTIFACTS
    }
    manifest = copy.deepcopy(manifest)
    manifest["artifacts"] = artifacts
    (target / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _copy_canonical(name: str) -> Path:
    target = INVALID_ROOT / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(CANONICAL, target)
    return target


def main() -> int:
    base_manifest = json.loads((CANONICAL / MANIFEST_NAME).read_text(encoding="utf-8"))

    # placeholder_commit: zero commit on runtime receipt
    d = _copy_canonical("placeholder_commit")
    receipt = json.loads((d / "runtime_receipt.json").read_text(encoding="utf-8"))
    receipt["source_commit"] = "0" * 40
    (d / "runtime_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    _write_manifest(d, base_manifest)

    # mismatched_certificate_id
    d = _copy_canonical("mismatched_certificate_id")
    vr = json.loads((d / "verification_result.json").read_text(encoding="utf-8"))
    verified = vr.get("verified_input")
    if isinstance(verified, dict):
        verified["certificate_id"] = "cert-trace-00000000-0000-0000-0000-000000000001"
    (d / "verification_result.json").write_text(json.dumps(vr, indent=2) + "\n", encoding="utf-8")
    _write_manifest(d, base_manifest)

    # mismatched_trace_hash
    d = _copy_canonical("mismatched_trace_hash")
    receipt = json.loads((d / "runtime_receipt.json").read_text(encoding="utf-8"))
    receipt["trace_hash"] = "sha256:" + "1" * 64
    (d / "runtime_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    _write_manifest(d, base_manifest)

    # mismatched_certified_bundle_hash
    d = _copy_canonical("mismatched_certified_bundle_hash")
    vr = json.loads((d / "verification_result.json").read_text(encoding="utf-8"))
    verified = vr.get("verified_input")
    if isinstance(verified, dict):
        verified["bundle_hash"] = "sha256:" + "2" * 64
    (d / "verification_result.json").write_text(json.dumps(vr, indent=2) + "\n", encoding="utf-8")
    _write_manifest(d, base_manifest)

    # failed_scientific_memory_import
    d = _copy_canonical("failed_scientific_memory_import")
    sm = json.loads((d / "scientific_memory_import_report.json").read_text(encoding="utf-8"))
    sm["verification_status"] = "failed"
    (d / "scientific_memory_import_report.json").write_text(json.dumps(sm, indent=2) + "\n", encoding="utf-8")
    _write_manifest(d, base_manifest)

    # legacy_import_mode
    d = _copy_canonical("legacy_import_mode")
    sm = json.loads((d / "scientific_memory_import_report.json").read_text(encoding="utf-8"))
    sm["allow_legacy"] = True
    sm["bundle_shape"] = "legacy"
    (d / "scientific_memory_import_report.json").write_text(json.dumps(sm, indent=2) + "\n", encoding="utf-8")
    _write_manifest(d, base_manifest)

    print(f"Wrote invalid release fixtures under {INVALID_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
