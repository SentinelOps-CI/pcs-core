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
    compatibility_dir,
    normalize_certifyedge_certificate_benchmark,
    normalize_labtrust_case_manifest,
    normalize_pf_explain_quality,
    normalize_pcs_bench_report,
    normalize_scientific_memory_render_benchmark,
)
from pcs_core.paths import examples_dir, repo_root  # noqa: E402
from pcs_core.validate import validate_file  # noqa: E402

PRODUCER_EXAMPLES = examples_dir() / "benchmark"


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    compat = compatibility_dir()

    pcs_dialect = json.loads((compat / "pcs_bench_report.dialect.json").read_text(encoding="utf-8"))
    _write_json(
        PRODUCER_EXAMPLES / "pcs_bench_report.valid.json",
        normalize_pcs_bench_report(pcs_dialect),
    )

    labtrust_dialect = json.loads(
        (compat / "labtrust_case_manifest.dialect.json").read_text(encoding="utf-8"),
    )
    _write_json(
        PRODUCER_EXAMPLES / "labtrust_case.valid.json",
        normalize_labtrust_case_manifest(labtrust_dialect),
    )

    certifyedge_dialect = json.loads(
        (compat / "certifyedge_certificate_benchmark.dialect.json").read_text(encoding="utf-8"),
    )
    _write_json(
        PRODUCER_EXAMPLES / "certifyedge_certificate_benchmark.valid.json",
        normalize_certifyedge_certificate_benchmark(certifyedge_dialect),
    )

    pf_dialect = json.loads(
        (compat / "pf_admission_explain_quality.dialect.json").read_text(encoding="utf-8"),
    )
    _write_json(
        PRODUCER_EXAMPLES / "pf_admission_benchmark.valid.json",
        normalize_pf_explain_quality(pf_dialect),
    )

    sm_dialect = json.loads(
        (compat / "scientific_memory_render_benchmark.dialect.json").read_text(encoding="utf-8"),
    )
    _write_json(
        PRODUCER_EXAMPLES / "scientific_memory_rendering_benchmark.valid.json",
        normalize_scientific_memory_render_benchmark(sm_dialect),
    )

    # pcs-core reference report from golden expected_reports (same as benchmark run output)
    report_src = (
        repo_root()
        / "benchmarks/labtrust-qc-release/expected_reports/benchmark_report.v0.json"
    )
    if not report_src.is_file():
        from pcs_core.benchmark_runner import run_benchmark_suite  # noqa: E402

        report = run_benchmark_suite("labtrust-qc-release-v0")
    else:
        report = json.loads(report_src.read_text(encoding="utf-8"))
    report["producer_id"] = "pcs-core"
    _write_json(PRODUCER_EXAMPLES / "pcs_core_benchmark_report.valid.json", report)

    for rel in (
        "examples/benchmark/pcs_bench_report.valid.json",
        "examples/benchmark/labtrust_case.valid.json",
        "examples/benchmark/certifyedge_certificate_benchmark.valid.json",
        "examples/benchmark/pf_admission_benchmark.valid.json",
        "examples/benchmark/scientific_memory_rendering_benchmark.valid.json",
        "examples/benchmark/pcs_core_benchmark_report.valid.json",
    ):
        validate_file(repo_root() / rel)

    print("Wrote examples/benchmark producer-validated examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
