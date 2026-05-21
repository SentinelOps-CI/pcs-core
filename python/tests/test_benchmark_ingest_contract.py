"""PcsBenchIngest.v0 and BenchmarkArtifactRef.v0 contract tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from pcs_core.benchmark_compat import build_pcs_bench_ingest
from pcs_core.hash import canonical_hash
from pcs_core.paths import examples_dir
from pcs_core.validate import ValidationError, validate_artifact, validate_file

INGEST_DIR = examples_dir() / "benchmark_ingest"


def _load_ingest(name: str) -> dict:
    path = INGEST_DIR / name
    if not path.is_file():
        pytest.skip("run python/scripts/materialize_benchmark_producer_examples.py")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "name",
    [
        "labtrust.pcs_bench_ingest.valid.json",
        "certifyedge.pcs_bench_ingest.valid.json",
        "provability_fabric.pcs_bench_ingest.valid.json",
        "scientific_memory.pcs_bench_ingest.valid.json",
    ],
)
def test_producer_ingest_has_bidirectional_refs(name: str) -> None:
    doc = _load_ingest(name)
    validate_artifact(doc, "PcsBenchIngest.v0")
    refs = doc.get("artifact_refs")
    assert isinstance(refs, list) and refs, f"{name} must include artifact_refs"
    for ref in refs:
        validate_artifact(ref, "BenchmarkArtifactRef.v0")


def test_ingest_rejects_mismatched_ref_digest() -> None:
    doc = _load_ingest("scientific_memory.pcs_bench_ingest.valid.json")
    bad = copy.deepcopy(doc)
    bad["artifact_refs"][0]["sha256"] = "sha256:" + "f" * 64
    with pytest.raises(ValidationError) as exc:
        validate_artifact(bad, "PcsBenchIngest.v0")
    assert any("sha256 does not match" in err for err in exc.value.errors)


def test_ingest_rejects_producer_without_refs() -> None:
    doc = _load_ingest("certifyedge.pcs_bench_ingest.valid.json")
    bad = copy.deepcopy(doc)
    del bad["artifact_refs"]
    with pytest.raises(ValidationError) as exc:
        validate_artifact(bad, "PcsBenchIngest.v0")
    assert any("requires artifact_refs" in err for err in exc.value.errors)


def test_ingest_rejects_orphan_ref() -> None:
    doc = _load_ingest("certifyedge.pcs_bench_ingest.valid.json")
    bad = copy.deepcopy(doc)
    bad["artifact_refs"].append(
        {
            "schema_version": "v0",
            "artifact_type": "BenchmarkRun.v0",
            "path": "runs/nonexistent.benchmark_run.v0.json",
            "sha256": "sha256:" + "a" * 64,
            "role": "producer_export",
            "source_repo": doc["source_repo"],
            "source_commit": doc["source_commit"],
            "signature_or_digest": "sha256:" + "b" * 64,
        },
    )
    with pytest.raises(ValidationError) as exc:
        validate_artifact(bad, "PcsBenchIngest.v0")
    assert any("no embedded objects" in err for err in exc.value.errors)


def test_ingest_rejects_duplicate_ref_paths() -> None:
    doc = _load_ingest("provability_fabric.pcs_bench_ingest.valid.json")
    bad = copy.deepcopy(doc)
    bad["artifact_refs"].append(copy.deepcopy(bad["artifact_refs"][0]))
    with pytest.raises(ValidationError) as exc:
        validate_artifact(bad, "PcsBenchIngest.v0")
    assert any("duplicate path" in err for err in exc.value.errors)


def test_benchmark_artifact_ref_example_validates() -> None:
    path = examples_dir() / "benchmarks" / "benchmark_artifact_ref.valid.json"
    if not path.is_file():
        pytest.skip("run python/scripts/materialize_benchmark_examples.py")
    validate_file(path)


def test_pcs_core_ingest_without_refs_allowed() -> None:
    body = build_pcs_bench_ingest(
        producer_id="pcs-core",
        suite_id="test-suite",
        workflow_id="test.workflow",
        source_repo="https://github.com/SentinelOps-CI/pcs-core",
    )
    validate_artifact(body, "PcsBenchIngest.v0")


def test_artifact_ref_record_digest() -> None:
    doc = _load_ingest("scientific_memory.pcs_bench_ingest.valid.json")
    ref = doc["artifact_refs"][0]
    expected = canonical_hash({k: v for k, v in ref.items() if k != "signature_or_digest"})
    assert ref["signature_or_digest"] == expected
