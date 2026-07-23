//! Fuzz harness scaffolding for pcs-core (Phase 7).
//!
//! Enable with cargo-fuzz when libfuzzer is available (see rust/FUZZING.md).
//! This binary exists so CI compiles the scaffold; it is not a libfuzzer target yet.

fn main() {
    eprintln!(
        "pcs-core fuzz scaffold: install cargo-fuzz and see rust/FUZZING.md for targets \
         (JSON, paths, hashes, manifests)."
    );
}

#[cfg(test)]
mod smoke {
    #[test]
    fn fuzz_scaffold_documents_targets() {
        assert_eq!(env!("CARGO_PKG_NAME"), "pcs-core");
    }
}
