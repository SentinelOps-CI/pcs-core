#!/usr/bin/env bash
# Provision CertifyEdge from pins/certifyedge.json (immutable strategies only).
# Fail-closed in PCS_RELEASE_MODE=release when the pin is unset / unpinned.
#
# Always emits a machine-readable environment file when provisioning succeeds:
#   ${OUT_DIR}/provision.env
# Fields: executable path, binary digest, version, pin identity, strategy, trust grade.
# Workflows MUST source this file and must NOT overwrite PF_CORE_CERTIFYEDGE_CLI
# with an empty repository secret.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIN_FILE="${PCS_CERTIFYEDGE_PIN:-${ROOT}/pins/certifyedge.json}"
MODE="${PCS_RELEASE_MODE:-preview}"
OUT_DIR="${PCS_CERTIFYEDGE_INSTALL_DIR:-${ROOT}/.tools/certifyedge}"
ENV_FILE="${PCS_CERTIFYEDGE_PROVISION_ENV:-${OUT_DIR}/provision.env}"

export PCS_RELEASE_MODE="${MODE}"

python3 "${ROOT}/scripts/verify-certifyedge-pin.py" --pin "${PIN_FILE}" --mode "${MODE}"

STATUS="$(python3 -c "import json,pathlib; print(json.loads(pathlib.Path(r'${PIN_FILE}').read_text(encoding='utf-8')).get('status',''))")"
STRATEGY="$(python3 -c "import json,pathlib; print(json.loads(pathlib.Path(r'${PIN_FILE}').read_text(encoding='utf-8')).get('provision_strategy','none'))")"
VERSION="$(python3 -c "import json,pathlib; print(json.loads(pathlib.Path(r'${PIN_FILE}').read_text(encoding='utf-8')).get('version','') or 'unknown')")"

write_provision_env() {
  local exe="$1"
  local digest="$2"
  local trust_grade="$3"
  local pin_identity
  pin_identity="$(python3 -c "import json,pathlib,sys; sys.path.insert(0, r'${ROOT}/python'); from pcs_core.certifyedge_pin import load_certifyedge_pin, pin_identity_from; p=json.loads(pathlib.Path(r'${PIN_FILE}').read_text(encoding='utf-8')); print(pin_identity_from(p))")"
  mkdir -p "$(dirname "${ENV_FILE}")"
  cat > "${ENV_FILE}" <<EOF
PCS_CERTIFYEDGE_EXECUTABLE=${exe}
PCS_CERTIFYEDGE_BINARY_DIGEST=${digest}
PCS_CERTIFYEDGE_VERSION=${VERSION}
PCS_CERTIFYEDGE_PIN_IDENTITY=${pin_identity}
PCS_CERTIFYEDGE_PROVISION_STRATEGY=${STRATEGY}
PCS_CERTIFYEDGE_TRUST_GRADE=${trust_grade}
PF_CORE_CERTIFYEDGE_CLI=${exe}
EOF
  echo "OK wrote provision env ${ENV_FILE}"
}

if [[ "${STATUS}" != "pinned" && "${STATUS}" != "dev_fixture" ]] || [[ "${STRATEGY}" == "none" || -z "${STRATEGY}" ]]; then
  if [[ "${MODE}" == "release" ]]; then
    echo "FAIL: cannot provision CertifyEdge in release mode without a pinned strategy" >&2
    exit 1
  fi
  echo "SKIP: CertifyEdge pin unpinned; not provisioning (mode=${MODE})"
  exit 0
fi

# Release mode rejects non-production strategies (including dev_fixture).
if [[ "${MODE}" == "release" && "${STRATEGY}" == "dev_fixture" ]]; then
  echo "FAIL: provision_strategy=dev_fixture is not allowed in release mode" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

case "${STRATEGY}" in
  oci_digest)
    IMAGE="$(python3 -c "import json,pathlib; p=json.loads(pathlib.Path(r'${PIN_FILE}').read_text(encoding='utf-8')); print(p['image'])")"
    DIGEST="$(python3 -c "import json,pathlib; p=json.loads(pathlib.Path(r'${PIN_FILE}').read_text(encoding='utf-8')); print(p['image_digest'])")"
    REF="${IMAGE%@*}@${DIGEST}"
    if ! command -v docker >/dev/null 2>&1; then
      echo "FAIL: docker required for oci_digest strategy" >&2
      exit 1
    fi
    echo "Pulling ${REF}"
    docker pull "${REF}"
    WRAPPER="${OUT_DIR}/certifyedge"
    cat > "${WRAPPER}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec docker run --rm -v "\$PWD:\$PWD" -w "\$PWD" "${REF}" "\$@"
EOF
    chmod +x "${WRAPPER}"
    # Wrapper script digest (not image layers); pin identity carries image digest.
    WRAP_DIGEST="$(python3 -c "import hashlib,pathlib; print('sha256:'+hashlib.sha256(pathlib.Path(r'${WRAPPER}').read_bytes()).hexdigest())")"
    write_provision_env "${WRAPPER}" "${WRAP_DIGEST}" "pinned"
    echo "OK provisioned CertifyEdge wrapper at ${WRAPPER}"
    echo "${WRAPPER}"
    ;;
  signed_binary)
    URL="$(python3 -c "import json,pathlib; print(json.loads(pathlib.Path(r'${PIN_FILE}').read_text(encoding='utf-8'))['binary_url'])")"
    EXPECTED="$(python3 -c "import json,pathlib; print(json.loads(pathlib.Path(r'${PIN_FILE}').read_text(encoding='utf-8'))['binary_sha256'])")"
    ARCHIVE="${OUT_DIR}/certifyedge"
    python3 - "${URL}" "${EXPECTED}" "${ARCHIVE}" <<'PY'
import hashlib, pathlib, sys, urllib.request
url, expected, dest = sys.argv[1], sys.argv[2].lower().removeprefix("sha256:"), pathlib.Path(sys.argv[3])
print(f"Downloading {url}", file=sys.stderr)
urllib.request.urlretrieve(url, dest)
digest = hashlib.sha256(dest.read_bytes()).hexdigest()
if digest != expected:
    raise SystemExit(f"FAIL binary checksum mismatch: got {digest}, expected {expected}")
print(f"OK binary sha256:{digest}", file=sys.stderr)
PY
    chmod +x "${ARCHIVE}"
    BIN_DIGEST="$(python3 -c "import hashlib,pathlib; print('sha256:'+hashlib.sha256(pathlib.Path(r'${ARCHIVE}').read_bytes()).hexdigest())")"
    write_provision_env "${ARCHIVE}" "${BIN_DIGEST}" "pinned"
    echo "OK provisioned CertifyEdge binary at ${ARCHIVE}"
    echo "${ARCHIVE}"
    ;;
  source_commit_build)
    REPO="$(python3 -c "import json,pathlib; print(json.loads(pathlib.Path(r'${PIN_FILE}').read_text(encoding='utf-8'))['source_repo'])")"
    COMMIT="$(python3 -c "import json,pathlib; print(json.loads(pathlib.Path(r'${PIN_FILE}').read_text(encoding='utf-8'))['source_commit'])")"
    SRC_DIR="${OUT_DIR}/src"
    rm -rf "${SRC_DIR}"
    git clone --filter=blob:none "${REPO}" "${SRC_DIR}"
    git -C "${SRC_DIR}" checkout --detach "${COMMIT}"
    ACTUAL="$(git -C "${SRC_DIR}" rev-parse HEAD)"
    if [[ "${ACTUAL}" != "${COMMIT}" ]]; then
      echo "FAIL: checked out ${ACTUAL}, expected ${COMMIT}" >&2
      exit 1
    fi
    if [[ -f "${SRC_DIR}/Cargo.toml" ]]; then
      (cd "${SRC_DIR}" && cargo build --release --locked)
      BIN="$(find "${SRC_DIR}/target/release" -maxdepth 1 -type f -name 'certifyedge*' ! -name '*.d' | head -n 1)"
    else
      echo "FAIL: unknown CertifyEdge build system under ${SRC_DIR}" >&2
      exit 1
    fi
    if [[ -z "${BIN}" || ! -f "${BIN}" ]]; then
      echo "FAIL: certifyedge binary not found after source build" >&2
      exit 1
    fi
    DEST="${OUT_DIR}/certifyedge"
    cp "${BIN}" "${DEST}"
    chmod +x "${DEST}"
    BIN_DIGEST="$(python3 -c "import hashlib,pathlib; print('sha256:'+hashlib.sha256(pathlib.Path(r'${DEST}').read_bytes()).hexdigest())")"
    write_provision_env "${DEST}" "${BIN_DIGEST}" "pinned"
    echo "OK provisioned CertifyEdge from ${COMMIT} at ${DEST}"
    echo "${DEST}"
    ;;
  dev_fixture)
    # Test/preview only — deterministic content-addressed fixture (not production).
    DEST="${OUT_DIR}/certifyedge"
    DIGEST="$(python3 "${ROOT}/scripts/certifyedge-dev-fixture.py" --out "${DEST}")"
    EXPECTED="$(python3 "${ROOT}/scripts/certifyedge-dev-fixture.py" --print-digest-only)"
    if [[ "${DIGEST}" != "${EXPECTED}" ]]; then
      echo "FAIL: dev fixture digest mismatch: ${DIGEST} != ${EXPECTED}" >&2
      exit 1
    fi
    # Also install a runnable stub wrapper for CLI smoke (separate from digest pin).
    RUNNER="${OUT_DIR}/certifyedge-run"
    cp "${ROOT}/scripts/certifyedge-stub.py" "${RUNNER}"
    chmod +x "${DEST}" "${RUNNER}" || true
    write_provision_env "${DEST}" "${DIGEST}" "untrusted_development"
    echo "OK provisioned CertifyEdge DEV FIXTURE at ${DEST} (trust_grade=untrusted_development)"
    echo "${DEST}"
    ;;
  *)
    echo "FAIL: unsupported provision_strategy=${STRATEGY}" >&2
    exit 1
    ;;
esac
