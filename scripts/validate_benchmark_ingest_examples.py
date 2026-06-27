#!/usr/bin/env python3
"""Validate every golden file under examples/benchmark_ingest/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from pcs_core.benchmark_ingest import (  # noqa: E402
    GOLDEN_INGEST_FILES,
    PRODUCER_INGEST_SOURCES,
    build_provenance_manifest,
    run_benchmark_ingest_contract_checks,
    summarize_ingest_adequacy,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-grade",
        action="store_true",
        help="Require release-grade or external-review-grade adequacy on each golden ingest",
    )
    parser.add_argument("--json", action="store_true", help="Emit adequacy summary JSON to stdout")
    parser.add_argument(
        "--write-provenance",
        action="store_true",
        help="Refresh examples/benchmark_ingest/provenance.manifest.json when checks pass",
    )
    args = parser.parse_args()

    errors = run_benchmark_ingest_contract_checks(check_release_grade=args.release_grade)
    adequacy = summarize_ingest_adequacy()
    manifest = build_provenance_manifest()

    if args.json:
        print(
            json.dumps(
                {
                    "status": "failed" if errors else "passed",
                    "errors": errors,
                    "adequacy": adequacy,
                    "provenance_manifest": manifest,
                },
                indent=2,
            ),
        )
        return 1 if errors else 0

    if errors:
        for err in errors:
            print(f"FAIL {err}", file=sys.stderr)
        return 1

    if args.write_provenance:
        import json

        from pcs_core.benchmark_ingest import INGEST_EXAMPLES_DIR
        from pcs_core.paths import repo_root

        manifest_path = INGEST_EXAMPLES_DIR / "provenance.manifest.json"
        manifest_path.write_text(
            json.dumps(build_provenance_manifest(), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {manifest_path.relative_to(repo_root()).as_posix()}")

    print(f"OK {len(GOLDEN_INGEST_FILES)} benchmark ingest examples")
    for name, meta in PRODUCER_INGEST_SOURCES.items():
        print(f"  {name}: {meta['producer_command']} ({meta['producer_repo']})")
    for row in adequacy:
        findings = row.get("findings") or []
        suffix = f" ({'; '.join(findings)})" if findings else ""
        print(f"  adequacy {row['file']}: {row['tier']}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
