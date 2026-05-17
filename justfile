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

ci: build python-test rust-test ts-test validate-examples hash-vectors-verify
    cd "{{root}}/python" && pcs schema check
    cd "{{root}}/python" && ruff check pcs_core tests
    cd "{{root}}/python" && ruff format --check pcs_core tests
    cd "{{root}}/rust" && cargo fmt --check
    cd "{{root}}/rust" && cargo clippy --all-targets -- -D warnings
