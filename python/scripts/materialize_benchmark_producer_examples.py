#!/usr/bin/env python3
"""Materialize examples/benchmark/*.valid.json from producer-shaped dialects."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from pcs_core.benchmark_compat import (  # noqa: E402
    build_certifyedge_pcs_bench_ingest,
    build_pf_pcs_bench_ingest,
    build_scientific_memory_pcs_bench_ingest,
    compatibility_dir,
    normalize_labtrust_case_manifest,
    normalize_pcs_bench_report,
)
from pcs_core.paths import examples_dir, repo_root  # noqa: E402
from pcs_core.validate import validate_file  # noqa: E402

PRODUCER_EXAMPLES = examples_dir() / "benchmark"

CANONICAL_EXAMPLES: tuple[tuple[str, str], ...] = (
    ("pcs_bench_report.valid.json", "BenchmarkReport.v0"),
    ("labtrust_benchmark_case.valid.json", "BenchmarkCase.v0"),
    ("certifyedge_pcs_bench_ingest.valid.json", "PcsBenchIngest.v0"),
    ("pf_pcs_bench_ingest.valid.json", "PcsBenchIngest.v0"),
    ("scientific_memory_pcs_bench_ingest.valid.json", "PcsBenchIngest.v0"),
)


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _remove_legacy_example_names() -> None:
    for legacy in (
        "labtrust_case.valid.json",
        "certifyedge_certificate_benchmark.valid.json",
        "pf_admission_benchmark.valid.json",
        "scientific_memory_rendering_benchmark.valid.json",
        "pcs_core_benchmark_report.valid.json",
    ):
        path = PRODUCER_EXAMPLES / legacy
        if path.is_file():
            path.unlink()


def main() -> int:
    compat = compatibility_dir()
    _remove_legacy_example_names()

    pcs_dialect = json.loads((compat / "pcs_bench_report.dialect.json").read_text(encoding="utf-8"))
    _write_json(
        PRODUCER_EXAMPLES / "pcs_bench_report.valid.json",
        normalize_pcs_bench_report(pcs_dialect),
    )

    labtrust_dialect = json.loads(
        (compat / "labtrust_case_manifest.dialect.json").read_text(encoding="utf-8"),
    )
    _write_json(
        PRODUCER_EXAMPLES / "labtrust_benchmark_case.valid.json",
        normalize_labtrust_case_manifest(labtrust_dialect),
    )

    certifyedge_dialect = json.loads(
        (compat / "certifyedge_certificate_benchmark.dialect.json").read_text(encoding="utf-8"),
    )
    _write_json(
        PRODUCER_EXAMPLES / "certifyedge_pcs_bench_ingest.valid.json",
        build_certifyedge_pcs_bench_ingest(certifyedge_dialect),
    )

    pf_explain = json.loads(
        (compat / "pf_admission_explain_quality.dialect.json").read_text(encoding="utf-8"),
    )
    pf_profile_path = compat / "pf_profile_coverage.dialect.json"
    pf_profile = (
        json.loads(pf_profile_path.read_text(encoding="utf-8")) if pf_profile_path.is_file() else None
    )
    _write_json(
        PRODUCER_EXAMPLES / "pf_pcs_bench_ingest.valid.json",
        build_pf_pcs_bench_ingest(pf_explain, pf_profile),
    )

    sm_dialect = json.loads(
        (compat / "scientific_memory_render_benchmark.dialect.json").read_text(encoding="utf-8"),
    )
    _write_json(
        PRODUCER_EXAMPLES / "scientific_memory_pcs_bench_ingest.valid.json",
        build_scientific_memory_pcs_bench_ingest(sm_dialect),
    )

    for rel, _artifact_type in CANONICAL_EXAMPLES:
        validate_file(repo_root() / "examples" / "benchmark" / rel.split("/")[-1])

    print("Wrote examples/benchmark producer-validated examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
