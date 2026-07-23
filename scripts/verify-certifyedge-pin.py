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
import re
import sys
from pathlib import Path

PLACEHOLDER_MARKERS = (
    "REPLACE_WITH",
    "REPLACE_ME",
    "example/certifyedge",
    "sha256:REPLACE",
)

DIGEST_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
COMMIT_RE = re.compile(r"^[a-f0-9]{40}$")


def _is_placeholder(value: str) -> bool:
    if not value or not value.strip():
        return True
    upper = value.upper()
    return any(marker.upper() in upper for marker in PLACEHOLDER_MARKERS)


def load_pin(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("pin root must be a JSON object")
    return data


def pin_is_production_ready(pin: dict) -> tuple[bool, list[str]]:
    """Return whether the pin can provision an immutable CertifyEdge binary."""
    errors: list[str] = []
    status = str(pin.get("status") or "").strip().lower()
    strategy = str(pin.get("provision_strategy") or "").strip().lower()

    if status != "pinned":
        errors.append(f"status is {status!r}; need 'pinned' for release provisioning")
    if strategy in {"", "none"}:
        errors.append("provision_strategy is unset (none)")
        return False, errors

    if strategy == "oci_digest":
        image = str(pin.get("image") or "")
        digest = str(pin.get("image_digest") or "")
        if _is_placeholder(image):
            errors.append("image is empty or placeholder")
        if not DIGEST_RE.match(digest) or _is_placeholder(digest):
            errors.append("image_digest must be sha256:<64 hex> (no placeholders)")
    elif strategy == "signed_binary":
        url = str(pin.get("binary_url") or "")
        digest = str(pin.get("binary_sha256") or "")
        if _is_placeholder(url):
            errors.append("binary_url is empty or placeholder")
        if not DIGEST_RE.match(digest) and not re.fullmatch(r"[a-f0-9]{64}", digest):
            errors.append("binary_sha256 must be sha256:<64 hex> or bare 64-hex digest")
        if _is_placeholder(digest):
            errors.append("binary_sha256 is placeholder")
    elif strategy == "source_commit_build":
        repo = str(pin.get("source_repo") or "")
        commit = str(pin.get("source_commit") or "")
        if _is_placeholder(repo):
            errors.append("source_repo is empty or placeholder")
        if not COMMIT_RE.match(commit):
            errors.append("source_commit must be a full 40-char git SHA")
    else:
        errors.append(
            f"unknown provision_strategy {strategy!r}; "
            "expected oci_digest | signed_binary | source_commit_build"
        )

    return not errors, errors


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
        help="release fails closed when pin unset; preview/dev allow unpinned",
    )
    args = parser.parse_args(argv)

    pin_path = args.pin
    if pin_path is None:
        root = Path(__file__).resolve().parents[1]
        pin_path = root / "pins" / "certifyedge.json"

    if not pin_path.is_file():
        print(f"FAIL: CertifyEdge pin missing: {pin_path}", file=sys.stderr)
        return 1

    try:
        pin = load_pin(pin_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: cannot read CertifyEdge pin: {exc}", file=sys.stderr)
        return 1

    ready, errors = pin_is_production_ready(pin)
    status = str(pin.get("status") or "unknown")
    strategy = str(pin.get("provision_strategy") or "none")

    if args.mode == "release":
        if not ready:
            print("FAIL: CertifyEdge pin is not production-ready for release mode:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            print(
                "Set pins/certifyedge.json status=pinned with a real immutable digest, "
                "or publish a technical preview under PCS_RELEASE_MODE=preview.",
                file=sys.stderr,
            )
            return 1
        print(f"OK CertifyEdge pin ready (strategy={strategy}, status={status})")
        return 0

    if ready:
        print(f"OK CertifyEdge pin ready (strategy={strategy}, status={status})")
    else:
        print(
            f"OK CertifyEdge pin unpinned for {args.mode} mode "
            f"(strategy={strategy}, status={status}); live attestation not provisionable"
        )
        for err in errors:
            print(f"  note: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
