"""Split pcs_core.validate into focused modules."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "pcs_core"
SOURCE = lines_source = ROOT / "validate.py"
# Reconstruct monolithic source from modules if validate.py is already split.
if "validate_detect import" in SOURCE.read_text(encoding="utf-8"):
    merged = []
    for name in ("validate_detect.py", "validate_pcs_core.py", "validate_pf_core.py", "validate_semantics.py"):
        part = (ROOT / name).read_text(encoding="utf-8")
        part = part.split('from __future__ import annotations\n', 1)[-1]
        merged.append(part)
    # Not reversible safely; use stored line backup
    backup = ROOT / "_validate_monolith_backup.py"
    if not backup.is_file():
        raise SystemExit("missing validate monolith backup; restore validate.py before split")
    lines = backup.read_text(encoding="utf-8").splitlines(keepends=True)
else:
    backup = ROOT / "_validate_monolith_backup.py"
    backup.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    lines = backup.read_text(encoding="utf-8").splitlines(keepends=True)

IMPORT_BLOCK = lines[1:35]

COMMON_IMPORTS = '''from pcs_core.paths import examples_dir as default_examples_dir
from pcs_core.paths import repo_root, schemas_dir
from pcs_core.registry_data import PF_CORE_CLAIM_CLASSES
from pcs_core.status import ARTIFACT_STATUSES, TRACE_CERTIFICATE_STATUSES

from pcs_core.lean_validate import (
    validate_lean_check_result_semantics,
    validate_proof_obligation_semantics,
)
from pcs_core.protocol_validate import (
    validate_artifact_registry_semantics,
    validate_conformance_report_semantics,
    validate_handoff_manifest_semantics,
    validate_release_chain_validation_result_semantics,
    validate_release_manifest_fixture_refs,
    validate_release_manifest_semantics,
)
from pcs_core.tool_use_validate import (
    validate_tool_use_certificate_semantics,
    validate_tool_use_trace_semantics,
    validate_workflow_profile_semantics,
)
from pcs_core.computation_validate import (
    validate_computation_run_receipt_semantics,
    validate_computation_witness_semantics,
    validate_dataset_receipt_semantics,
    validate_environment_receipt_semantics,
    validate_result_artifact_semantics,
)
from pcs_core.benchmark_validate import (
    validate_benchmark_case_semantics,
    validate_benchmark_metric_registry_semantics,
    validate_benchmark_registry_semantics,
    validate_benchmark_report_semantics,
    validate_benchmark_run_semantics,
    validate_benchmark_suite_manifest_semantics,
    validate_benchmark_task_semantics,
)
from pcs_core.benchmark_validate import validate_pcs_bench_ingest_semantics
'''


def join(parts: list[str]) -> str:
    return "".join(parts)


detect = (
    join(IMPORT_BLOCK[:2])
    + join(IMPORT_BLOCK[2:9])
    + COMMON_IMPORTS
    + join(lines[35:93])
    + join(lines[113:119])
    + join(lines[138:508])
)

pcs = (
    join(IMPORT_BLOCK[:2])
    + "from typing import Any\n\n"
    + "from pcs_core.status import ARTIFACT_STATUSES, TRACE_CERTIFICATE_STATUSES\n\n"
    + join(lines[94:109])
    + join(lines[510:653])
)

pf = (
    join(IMPORT_BLOCK[:2])
    + "import json\nfrom pathlib import Path\nfrom typing import Any\n\n"
    + "from pcs_core.validate_detect import ValidationError, detect_artifact_type\n\n"
    + join(lines[121:134])
    + join(lines[654:764])
    + join(lines[1044:1270])
)

sem = (
    join(IMPORT_BLOCK[:2])
    + join(IMPORT_BLOCK[2:9])
    + COMMON_IMPORTS
    + "from pcs_core.validate_detect import (\n"
    + "    ARTIFACT_SCHEMAS,\n"
    + "    ValidationError,\n"
    + "    detect_artifact_type,\n"
    + "    get_validator,\n"
    + "    validate_schema,\n"
    + "    _load_schema,\n"
    + ")\n"
    + "from pcs_core.validate_pcs_core import (\n"
    + "    _check_source_commits,\n"
    + "    _validate_science_claim_bundle,\n"
    + "    _validate_signed_bundle,\n"
    + "    _validate_status_fields,\n"
    + "    _validate_verification_result,\n"
    + ")\n"
    + "from pcs_core.validate_pf_core import (\n"
    + "    _PF_CORE_ARTIFACT_TYPES,\n"
    + "    _validate_lean_check_result,\n"
    + "    _validate_pfcore_certificate,\n"
    + "    _validate_pfcore_claim_class,\n"
    + "    _validate_pfcore_trace,\n"
    + ")\n\n"
    + join(lines[765:1043])
    + join(lines[1270:])
)

(ROOT / "validate_detect.py").write_text(
    '"""Artifact type detection and JSON Schema validation."""\n' + detect,
    encoding="utf-8",
)
(ROOT / "validate_pcs_core.py").write_text(
    '"""PCS core semantic validation helpers."""\n' + pcs,
    encoding="utf-8",
)
(ROOT / "validate_pf_core.py").write_text(
    '"""PF-Core semantic validation and fixture harness."""\n' + pf,
    encoding="utf-8",
)
(ROOT / "validate_semantics.py").write_text(
    '"""Semantic validation orchestration and public validate API."""\n' + sem,
    encoding="utf-8",
)
(ROOT / "validate.py").write_text(
    '"""JSON Schema and semantic validation for PCS artifacts."""\n\n'
    "from pcs_core.validate_detect import *  # noqa: F403\n"
    "from pcs_core.validate_pcs_core import *  # noqa: F403\n"
    "from pcs_core.validate_pf_core import *  # noqa: F403\n"
    "from pcs_core.validate_semantics import *  # noqa: F403\n",
    encoding="utf-8",
)
print("split complete")
