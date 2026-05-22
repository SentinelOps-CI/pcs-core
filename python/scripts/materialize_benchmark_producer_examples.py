#!/usr/bin/env python3
"""Materialize producer benchmark examples from repo-shaped dialect fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from pcs_core.benchmark_ingest import build_provenance_manifest  # noqa: E402
from pcs_core.benchmark_compat import (  # noqa: E402
    INGEST_NORMALIZERS,
    build_certifyedge_pcs_bench_ingest,
    build_labtrust_pcs_bench_ingest,
    build_pf_pcs_bench_ingest,
    build_scientific_memory_pcs_bench_ingest,
    compatibility_dir,
    normalize_labtrust_case_manifest,
    normalize_pf_pcs_bench_ingest_dialect,
    normalize_pcs_bench_report,
)
from pcs_core.paths import examples_dir, repo_root  # noqa: E402
from pcs_core.validate import validate_file  # noqa: E402

PRODUCER_EXAMPLES = examples_dir() / "benchmark"
INGEST_EXAMPLES = examples_dir() / "benchmark_ingest"

CANONICAL_EXAMPLES: tuple[tuple[str, str], ...] = (
    ("pcs_bench_report.valid.json", "BenchmarkReport.v0"),
    ("labtrust_benchmark_case.valid.json", "BenchmarkCase.v0"),
)

INGEST_CANONICAL: tuple[tuple[str, str], ...] = (
    ("labtrust.pcs_bench_ingest.valid.json", "PcsBenchIngest.v0"),
    ("certifyedge.pcs_bench_ingest.valid.json", "PcsBenchIngest.v0"),
    ("provability_fabric.pcs_bench_ingest.valid.json", "PcsBenchIngest.v0"),
    ("scientific_memory.pcs_bench_ingest.valid.json", "PcsBenchIngest.v0"),
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
        "certifyedge_pcs_bench_ingest.valid.json",
        "pf_pcs_bench_ingest.valid.json",
        "scientific_memory_pcs_bench_ingest.valid.json",
    ):
        for root in (PRODUCER_EXAMPLES, INGEST_EXAMPLES):
            path = root / legacy
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

    labtrust_case_path = (
        repo_root()
        / "benchmarks/labtrust-qc-release/valid/labtrust-valid-release-v0/benchmark_case.v0.json"
    )
    run_path = (
        repo_root()
        / "benchmarks/labtrust-qc-release/valid/labtrust-valid-release-v0/"
        "benchmark_run.labtrust-valid-release-v0.v0.json"
    )
    if labtrust_case_path.is_file() and run_path.is_file():
        from pcs_core.benchmark_runner import execute_benchmark_case, load_benchmark_case  # noqa: E402

        case = load_benchmark_case(labtrust_case_path)
        _write_json(PRODUCER_EXAMPLES / "labtrust_benchmark_case.valid.json", case)
        run = execute_benchmark_case(case)
        _write_json(
            INGEST_EXAMPLES / "labtrust.pcs_bench_ingest.valid.json",
            build_labtrust_pcs_bench_ingest(
                case=case,
                run=run,
                run_path="valid/labtrust-valid-release-v0/benchmark_run.labtrust-valid-release-v0.v0.json",
            ),
        )
    else:
        labtrust_dialect = json.loads(
            (compat / "labtrust_case_manifest.dialect.json").read_text(encoding="utf-8"),
        )
        case = normalize_labtrust_case_manifest(labtrust_dialect)
        _write_json(PRODUCER_EXAMPLES / "labtrust_benchmark_case.valid.json", case)
        from pcs_core.benchmark_runner import execute_benchmark_case  # noqa: E402

        try:
            run = execute_benchmark_case(case)
            _write_json(
                INGEST_EXAMPLES / "labtrust.pcs_bench_ingest.valid.json",
                build_labtrust_pcs_bench_ingest(
                    case=case,
                    run=run,
                    run_path="valid/labtrust-valid-release-v0/benchmark_run.labtrust-valid-release-v0.v0.json",
                ),
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"warn: skipped labtrust ingest (gallery unavailable): {exc}", file=sys.stderr)

    certifyedge_dialect = json.loads(
        (compat / "certifyedge_certificate_benchmark.dialect.json").read_text(encoding="utf-8"),
    )
    _write_json(
        INGEST_EXAMPLES / "certifyedge.pcs_bench_ingest.valid.json",
        build_certifyedge_pcs_bench_ingest(certifyedge_dialect),
    )

    pf_explain = json.loads(
        (compat / "pf_admission_explain_quality.dialect.json").read_text(encoding="utf-8"),
    )
    _write_json(
        INGEST_EXAMPLES / "provability_fabric.pcs_bench_ingest.valid.json",
        normalize_pf_pcs_bench_ingest_dialect(pf_explain),
    )

    sm_dialect = json.loads(
        (compat / "scientific_memory_render_benchmark.dialect.json").read_text(encoding="utf-8"),
    )
    _write_json(
        INGEST_EXAMPLES / "scientific_memory.pcs_bench_ingest.valid.json",
        build_scientific_memory_pcs_bench_ingest(sm_dialect),
    )

    for rel, _artifact_type in CANONICAL_EXAMPLES:
        validate_file(PRODUCER_EXAMPLES / rel)
    for rel, _artifact_type in INGEST_CANONICAL:
        validate_file(INGEST_EXAMPLES / rel)

    for dialect_name, (_artifact_type, normalizer) in INGEST_NORMALIZERS.items():
        dialect_path = compat / dialect_name
        if not dialect_path.is_file():
            continue
        raw = json.loads(dialect_path.read_text(encoding="utf-8"))
        ingest = normalizer(raw)
        out_name = dialect_name.replace(".dialect.json", ".pcs_bench_ingest.normalized.json")
        _write_json(compat / out_name, ingest)

    certifyedge_ingest = json.loads(
        (INGEST_EXAMPLES / "certifyedge.pcs_bench_ingest.valid.json").read_text(encoding="utf-8"),
    )
    missing_refs = dict(certifyedge_ingest)
    missing_refs.pop("artifact_refs", None)
    _write_json(examples_dir() / "invalid_pcs_bench_ingest_missing_refs.json", missing_refs)
    bad_digest = json.loads(
        (INGEST_EXAMPLES / "certifyedge.pcs_bench_ingest.valid.json").read_text(encoding="utf-8"),
    )
    bad_digest["artifact_refs"] = [
        {
            **bad_digest["artifact_refs"][0],
            "sha256": "sha256:" + "f" * 64,
        },
    ]
    _write_json(examples_dir() / "invalid_pcs_bench_ingest_bad_ref_digest.json", bad_digest)

    _write_json(INGEST_EXAMPLES / "provenance.manifest.json", build_provenance_manifest())
    validate_file(INGEST_EXAMPLES / "labtrust.pcs_bench_ingest.valid.json")

    print("Wrote examples/benchmark and examples/benchmark_ingest producer-validated examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
