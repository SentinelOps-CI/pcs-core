set shell := ["bash", "-cu"]

root := justfile_directory()

default:
    @just ci

build:
    cd "{{root}}/python" && pip install -e ".[dev]"
    cd "{{root}}/rust" && cargo build
    cd "{{root}}/typescript" && npm install && npm run build

validate-examples:
    cd "{{root}}/python" && pcs examples check

labtrust-check:
    cd "{{root}}/python" && pytest -q tests/test_labtrust_conformance.py

generate-labtrust-release-fixtures:
    cd "{{root}}/python" && python -m pcs_core.release_fixtures --write

validate-labtrust-release-fixtures:
    cd "{{root}}/python" && pcs validate-release-manifest ../examples/labtrust-release/RELEASE_FIXTURE_MANIFEST.json

pcs-v01-clean-chain:
    pwsh -File "{{root}}/scripts/run-pcs-v01-clean-chain.ps1"

python-test:
    cd "{{root}}/python" && pytest -q

rust-test:
    cd "{{root}}/rust" && cargo test

ts-test:
    cd "{{root}}/typescript" && npm test

hash-vectors-write:
    cd "{{root}}/python" && python -m pcs_core.hash_vectors --write

hash-vectors-verify:
    cd "{{root}}/python" && python -m pcs_core.hash_vectors --verify

pcs-schema-diff vendor_dir="schemas":
    bash "{{root}}/scripts/pcs-schema-diff.sh" "{{root}}/{{vendor_dir}}"

ci: build python-test rust-test ts-test validate-examples labtrust-check validate-labtrust-release-fixtures hash-vectors-verify pcs-schema-diff
    cd "{{root}}/python" && pcs schema check
    cd "{{root}}/python" && ruff check pcs_core tests
    cd "{{root}}/python" && ruff format --check pcs_core tests
    cd "{{root}}/rust" && cargo fmt --check
    cd "{{root}}/rust" && cargo clippy --all-targets -- -D warnings
