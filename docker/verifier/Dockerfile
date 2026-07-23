# syntax=docker/dockerfile:1.7

# PCS verifier distribution (OCI).
# Base image pinned by digest (pins/python-base-image.json). Image signing,
# SBOM, and provenance attestations are documented in docs/distribution.md.

# Multi-platform index digest for python:3.12-slim-bookworm
ARG PYTHON_IMAGE=python@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b
FROM ${PYTHON_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ELAN_HOME=/opt/elan \
    PATH="/opt/elan/bin:${PATH}" \
    PCS_PRODUCT=verifier \
    HOME=/home/pcs

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 pcs \
    && useradd --system --uid 10001 --gid pcs --create-home --home-dir /home/pcs pcs \
    && mkdir -p /opt/elan /opt/pcs-core /work \
    && chown -R pcs:pcs /opt/elan /opt/pcs-core /work /home/pcs

# Pin elan by version + sha256 (pins/elan.json). Fail closed on mismatch.
COPY --chown=pcs:pcs pins/elan.json /tmp/elan.json
USER pcs
RUN set -eux; \
    ELAN_VERSION="$(python3 -c 'import json; print(json.load(open("/tmp/elan.json"))["version"])')"; \
    ELAN_SHA="$(python3 -c 'import json; print(json.load(open("/tmp/elan.json"))["sha256"])')"; \
    ELAN_URL="$(python3 -c 'import json; print(json.load(open("/tmp/elan.json"))["url"])')"; \
    LEAN_TC="$(python3 -c 'import json; print(json.load(open("/tmp/elan.json"))["default_lean_toolchain"])')"; \
    curl -sSfL "$ELAN_URL" -o /tmp/elan.tar.gz; \
    echo "${ELAN_SHA}  /tmp/elan.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/elan.tar.gz -C /tmp; \
    ELAN_HOME=/opt/elan /tmp/elan-init -y --default-toolchain none --no-modify-path; \
    /opt/elan/bin/elan default "$LEAN_TC"; \
    rm -rf /tmp/elan.tar.gz /tmp/elan-init /tmp/elan.json

WORKDIR /opt/pcs-core

USER root
COPY --chown=pcs:pcs schemas ./schemas
COPY --chown=pcs:pcs catalog ./catalog
COPY --chown=pcs:pcs lean ./lean
COPY --chown=pcs:pcs python ./python
COPY --chown=pcs:pcs pins ./pins
COPY --chown=pcs:pcs test_vectors ./test_vectors
COPY --chown=pcs:pcs VERSION ./VERSION

USER pcs
RUN pip install --user --no-cache-dir -e "./python" \
    && cd lean \
    && lake build PCS \
    && lake build PFCore

ENV PATH="/home/pcs/.local/bin:${PATH}"

WORKDIR /work
ENTRYPOINT ["pcs"]
CMD ["capabilities"]

LABEL org.opencontainers.image.title="pcs-core-verifier" \
      org.opencontainers.image.description="PCS Lean verifier distribution" \
      org.opencontainers.image.source="https://github.com/SentinelOps-CI/pcs-core" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.base.name="docker.io/library/python:3.12-slim-bookworm" \
      org.opencontainers.image.base.digest="sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b"
