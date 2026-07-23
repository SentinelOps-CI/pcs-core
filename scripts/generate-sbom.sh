#!/usr/bin/env bash
# SPDX / CycloneDX SBOM scaffolding for release bundles.
# Prefers cdxgen or syft when installed; otherwise emits a minimal CycloneDX stub.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-${ROOT}/dist/sbom}"
mkdir -p "${OUT_DIR}"
VERSION="$(tr -d '\r\n' < "${ROOT}/VERSION")"

if command -v cdxgen >/dev/null 2>&1; then
  cdxgen -o "${OUT_DIR}/pcs-core.cdx.json" -t python,rust,npm,docker "${ROOT}"
  echo "OK CycloneDX via cdxgen: ${OUT_DIR}/pcs-core.cdx.json"
  exit 0
fi

if command -v syft >/dev/null 2>&1; then
  SYFT_ROOT="${ROOT}"
  if command -v cygpath >/dev/null 2>&1; then
    SYFT_ROOT="$(cygpath -w "${ROOT}")"
  fi
  if syft "dir:${SYFT_ROOT}" -o cyclonedx-json="${OUT_DIR}/pcs-core.cdx.json" \
    -o spdx-json="${OUT_DIR}/pcs-core.spdx.json"; then
    echo "OK SBOM via syft: ${OUT_DIR}/pcs-core.cdx.json"
    exit 0
  fi
  echo "WARN: syft failed for ${SYFT_ROOT}; falling back to scaffold SBOM"
fi

python3 - <<PY
import json
from pathlib import Path

out = Path(r"${OUT_DIR}") / "pcs-core.cdx.json"
doc = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.5",
    "version": 1,
    "metadata": {
        "component": {
            "type": "application",
            "name": "pcs-core",
            "version": "${VERSION}",
            "bom-ref": "pkg:github/SentinelOps-CI/pcs-core@${VERSION}",
        },
        "tools": [{"name": "pcs-core/scripts/generate-sbom.sh", "version": "scaffold"}],
    },
    "components": [
        {
            "type": "library",
            "name": "jsonschema",
            "purl": "pkg:pypi/jsonschema",
            "scope": "required",
        },
        {
            "type": "library",
            "name": "referencing",
            "purl": "pkg:pypi/referencing",
            "scope": "required",
        },
    ],
    "notes": [
        "Scaffold SBOM: install cdxgen or syft for a complete inventory.",
        "Pins: pins/elan.json, pins/certifyedge.json, pins/github-actions.json, rust/Cargo.lock, typescript/package-lock.json, python/requirements.lock",
    ],
}
out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
print(f"OK scaffold CycloneDX: {out}")
PY
