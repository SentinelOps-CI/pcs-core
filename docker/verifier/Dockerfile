# syntax=docker/dockerfile:1.7

# PCS verifier distribution (OCI scaffold).
# Ships pinned Lean toolchain assets + pcs-core with Lean sources for PF-Core / PCS
# envelope verification. Image signing (cosign/sigstore) is documented in
# docs/distribution.md; enable once org signing keys are available.

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.elan/bin:${PATH}" \
    PCS_PRODUCT=verifier

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git build-essential \
    && rm -rf /var/lib/apt/lists/*

# Pin elan by version + sha256 (pins/elan.json). Fail closed on mismatch.
COPY pins/elan.json /tmp/elan.json
RUN set -eux; \
    ELAN_VERSION="$(python3 -c 'import json; print(json.load(open("/tmp/elan.json"))["version"])')"; \
    ELAN_SHA="$(python3 -c 'import json; print(json.load(open("/tmp/elan.json"))["sha256"])')"; \
    ELAN_URL="$(python3 -c 'import json; print(json.load(open("/tmp/elan.json"))["url"])')"; \
    LEAN_TC="$(python3 -c 'import json; print(json.load(open("/tmp/elan.json"))["default_lean_toolchain"])')"; \
    curl -sSfL "$ELAN_URL" -o /tmp/elan.tar.gz; \
    echo "${ELAN_SHA}  /tmp/elan.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/elan.tar.gz -C /tmp; \
    /tmp/elan-init -y --default-toolchain none; \
    elan default "$LEAN_TC"; \
    rm -rf /tmp/elan.tar.gz /tmp/elan-init /tmp/elan.json

WORKDIR /opt/pcs-core

COPY schemas ./schemas
COPY catalog ./catalog
COPY lean ./lean
COPY python ./python
COPY pins ./pins
COPY test_vectors ./test_vectors
COPY VERSION ./VERSION

RUN pip install --no-cache-dir -e "./python" \
    && cd lean \
    && lake build PCS \
    && lake build PFCore

WORKDIR /work
ENTRYPOINT ["pcs"]
CMD ["capabilities"]

LABEL org.opencontainers.image.title="pcs-core-verifier" \
      org.opencontainers.image.description="PCS Lean verifier distribution" \
      org.opencontainers.image.source="https://github.com/SentinelOps-CI/pcs-core" \
      org.opencontainers.image.licenses="Apache-2.0"
