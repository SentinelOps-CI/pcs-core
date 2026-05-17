#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANONICAL="${ROOT}/schemas"
VENDOR="${1:-}"

if [[ -z "${VENDOR}" ]]; then
  echo "usage: pcs-schema-diff.sh <vendor_schemas_dir>" >&2
  echo "Compare vendored PCS schemas to ${CANONICAL}" >&2
  exit 2
fi

if [[ ! -d "${VENDOR}" ]]; then
  echo "vendor schemas directory not found: ${VENDOR}" >&2
  exit 1
fi

if diff -ru "${CANONICAL}" "${VENDOR}"; then
  echo "OK: no schema drift (${VENDOR})"
else
  echo "FAIL: schema drift detected between ${CANONICAL} and ${VENDOR}" >&2
  exit 1
fi
