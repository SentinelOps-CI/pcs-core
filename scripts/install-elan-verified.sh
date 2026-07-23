#!/usr/bin/env bash
# Install elan after verifying the pinned archive checksum (pins/elan.json).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIN_FILE="${ROOT}/pins/elan.json"

if [[ ! -f "${PIN_FILE}" ]]; then
  echo "FAIL: missing ${PIN_FILE}" >&2
  exit 1
fi

ARCHIVE_PATH="$(python3 - "${PIN_FILE}" <<'PY'
import hashlib
import json
import pathlib
import sys
import urllib.request

pin_path = pathlib.Path(sys.argv[1])
pin = json.loads(pin_path.read_text(encoding="utf-8"))
url = pin["url"]
expected = str(pin["sha256"]).lower().removeprefix("sha256:")
archive = pathlib.Path("/tmp") / pin["archive"]
print(f"Downloading {url}", file=sys.stderr)
urllib.request.urlretrieve(url, archive)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
if digest != expected:
    raise SystemExit(f"FAIL elan checksum mismatch: got {digest}, expected {expected}")
print(f"OK elan sha256:{digest}", file=sys.stderr)
print(archive)
PY
)"

LEAN_TC="$(python3 -c "import json,pathlib; print(json.loads(pathlib.Path(r'${PIN_FILE}').read_text())['default_lean_toolchain'])")"

tar -xzf "${ARCHIVE_PATH}" -C /tmp
/tmp/elan-init -y --default-toolchain none
export PATH="${HOME}/.elan/bin:${PATH}"
elan default "${LEAN_TC}"
echo "OK elan installed; default toolchain ${LEAN_TC}"
