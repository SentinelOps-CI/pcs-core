"""BenchmarkMetricRegistry.v0 loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.benchmark_metric_registry_data import benchmark_metric_entries
from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.paths import examples_dir
from pcs_core.validate import ValidationError, validate_artifact

REGISTRY_ID = "pcs-benchmark-metric-registry-v0"
REGISTRY_VERSION = "0.1.0"


def build_benchmark_metric_registry() -> dict[str, Any]:
    body = {
        "schema_version": "v0",
        "registry_id": REGISTRY_ID,
        "registry_version": REGISTRY_VERSION,
        "metrics": benchmark_metric_entries(),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    body["signature_or_digest"] = canonical_hash(body)
    return body


def default_benchmark_metric_registry_path() -> Path:
    return examples_dir() / "benchmark_metric_registry.valid.json"


def load_benchmark_metric_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or default_benchmark_metric_registry_path()
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationError(f"{registry_path}: registry root must be a JSON object")
    validate_artifact(data, "BenchmarkMetricRegistry.v0")
    return data
