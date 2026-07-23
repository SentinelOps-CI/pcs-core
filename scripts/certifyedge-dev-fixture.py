#!/usr/bin/env python3
"""Deterministic CertifyEdge development fixture (NOT production).

Writes a content-addressed fixture binary whose SHA-256 is stable across
platforms. Used only with provision_strategy=dev_fixture for tests/preview.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

# Keep in sync with pcs_core.certifyedge_pin.DEV_FIXTURE_MARKER
DEV_FIXTURE_MARKER = b"PCS_CERTIFYEDGE_DEV_FIXTURE_V1\n"


def fixture_digest() -> str:
    return f"sha256:{hashlib.sha256(DEV_FIXTURE_MARKER).hexdigest()}"


def write_fixture(dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(DEV_FIXTURE_MARKER)
    return f"sha256:{hashlib.sha256(dest.read_bytes()).hexdigest()}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Destination path for the fixture binary bytes",
    )
    parser.add_argument(
        "--print-digest-only",
        action="store_true",
        help="Print the expected digest and exit without writing",
    )
    args = parser.parse_args(argv)
    if args.print_digest_only:
        print(fixture_digest())
        return 0
    if args.out is None:
        parser.error("--out is required unless --print-digest-only is set")
    digest = write_fixture(args.out)
    print(digest)
    if digest != fixture_digest():
        print("FAIL: fixture digest drift", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
