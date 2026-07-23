#!/usr/bin/env python3
"""Fail-closed org/infrastructure release gate checker.

Exit codes:
  0 — all hard gates passed for the requested mode
  1 — one or more hard failures (stable/release fail-closed)
  2 — usage error

See docs/pf-core/operator-release-gates.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_PY = _REPO / "python"
if _PY.is_dir() and str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))

from pcs_core.release_gates import run_release_gate_check  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("release", "preview", "dev"),
        default=None,
        help="Override PCS_RELEASE_MODE (default: env or preview)",
    )
    parser.add_argument(
        "--pin",
        type=Path,
        default=None,
        help="Path to pins/certifyedge.json",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="TrustedKeyRegistry.v0 JSON (else PCS_TRUSTED_KEY_REGISTRY)",
    )
    parser.add_argument(
        "--release-root",
        type=Path,
        default=None,
        help="Optional release/bundle root for ArtifactIntegrity signature verify",
    )
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        default=None,
        help="Optional provenance package dir (ReleaseProvenanceBinding.v0.json)",
    )
    parser.add_argument(
        "--require-oci-publish",
        action="store_true",
        help="Fail release mode when PCS_VERIFIER_OCI_DIGEST is unset",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit ReleaseGateCheckReport.v0 JSON",
    )
    args = parser.parse_args(argv)

    code, text = run_release_gate_check(
        mode=args.mode,
        pin_path=args.pin,
        registry_path=args.registry,
        release_root=args.release_root,
        provenance_dir=args.provenance_dir,
        require_oci_publish=args.require_oci_publish,
        as_json=args.json,
    )
    if code == 0:
        sys.stdout.write(text)
    else:
        # Hard failures go to stderr for CI log scanning; JSON always stdout.
        if args.json:
            sys.stdout.write(text)
        else:
            sys.stderr.write(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
