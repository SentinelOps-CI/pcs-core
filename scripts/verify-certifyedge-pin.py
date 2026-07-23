#!/usr/bin/env python3
"""Verify CertifyEdge pin file for release vs preview modes (fail-closed).

Exit codes:
  0 — pin acceptable for the requested mode
  1 — pin missing / invalid / unset in release mode
  2 — usage error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from a checkout without PYTHONPATH when pcs-core is not installed.
_REPO = Path(__file__).resolve().parents[1]
_PY = _REPO / "python"
if _PY.is_dir() and str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))

from pcs_core.certifyedge_pin import (  # noqa: E402
    load_certifyedge_pin,
    pin_allows_dev_fixture,
    pin_is_production_ready,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pin",
        type=Path,
        default=None,
        help="Path to pins/certifyedge.json (default: repo pins/certifyedge.json)",
    )
    parser.add_argument(
        "--mode",
        choices=("release", "preview", "dev"),
        default="preview",
        help="release fails closed when pin unset; preview/dev allow unpinned or dev_fixture",
    )
    args = parser.parse_args(argv)

    pin_path = args.pin
    if pin_path is None:
        pin_path = _REPO / "pins" / "certifyedge.json"

    if not pin_path.is_file():
        print(f"FAIL: CertifyEdge pin missing: {pin_path}", file=sys.stderr)
        return 1

    try:
        pin = load_certifyedge_pin(pin_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: cannot read CertifyEdge pin: {exc}", file=sys.stderr)
        return 1

    ready, errors = pin_is_production_ready(pin)
    status = pin.status
    strategy = pin.provision_strategy

    if args.mode == "release":
        if not ready:
            print("FAIL: CertifyEdge pin is not production-ready for release mode:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            print(
                "Set pins/certifyedge.json status=pinned with a real immutable digest "
                "(oci_digest | signed_binary | source_commit_build). "
                "Do not invent placeholder digests. "
                "dev_fixture is test/preview only. "
                "Or publish a technical preview under PCS_RELEASE_MODE=preview.",
                file=sys.stderr,
            )
            return 1
        print(f"OK CertifyEdge pin ready (strategy={strategy}, status={status})")
        return 0

    # preview / dev
    if ready:
        print(f"OK CertifyEdge pin ready (strategy={strategy}, status={status})")
        return 0

    if strategy == "dev_fixture":
        ok, fixture_errors = pin_allows_dev_fixture(pin)
        if ok:
            print(
                f"OK CertifyEdge DEV FIXTURE pin acceptable for {args.mode} "
                f"(strategy={strategy}, status={status}); trust_grade=untrusted_development"
            )
            return 0
        print("FAIL: invalid CertifyEdge dev_fixture pin:", file=sys.stderr)
        for err in fixture_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(
        f"OK CertifyEdge pin unpinned for {args.mode} mode "
        f"(strategy={strategy}, status={status}); live attestation not provisionable"
    )
    for err in errors:
        print(f"  note: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
