"""BenchmarkRegistry.v0 loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.benchmark_registry_data import benchmark_suite_entries
from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.paths import examples_dir
from pcs_core.validate import ValidationError, validate_artifact

REGISTRY_ID = "pcs-benchmark-registry-v0"
REGISTRY_VERSION = "0.1.0"


def build_benchmark_registry() -> dict[str, Any]:
    body = {
        "schema_version": "v0",
        "registry_id": REGISTRY_ID,
        "registry_version": REGISTRY_VERSION,
        "suites": benchmark_suite_entries(),
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    body["signature_or_digest"] = canonical_hash(body)
    return body


def default_benchmark_registry_path() -> Path:
    return examples_dir() / "benchmark_registry.valid.json"


def load_benchmark_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or default_benchmark_registry_path()
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationError(f"{registry_path}: registry root must be an object")
    validate_artifact(data, "BenchmarkRegistry.v0")
    return data
