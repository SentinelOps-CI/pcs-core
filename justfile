set shell := ["bash", "-cu"]

root := justfile_directory()

default:
    @just ci

build:
    cd "{{root}}/python" && pip install -e ".[dev]"
    cd "{{root}}/rust" && cargo build
    cd "{{root}}/typescript" && npm install && npm run build

test: python-test rust-test ts-test

python-test:
    cd "{{root}}/python" && pytest -q

rust-test:
    cd "{{root}}/rust" && cargo test

ts-test:
    cd "{{root}}/typescript" && npm test

validate-examples:
    cd "{{root}}/python" && pcs examples check

lake-build:
    cd "{{root}}/lean" && lake build

ci: build test validate-examples lake-build
    cd "{{root}}/python" && pcs schema check
    cd "{{root}}/python" && ruff check pcs_core tests
    cd "{{root}}/rust" && cargo fmt --check
    cd "{{root}}/typescript" && npm run lint
