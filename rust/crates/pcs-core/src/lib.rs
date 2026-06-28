pub mod hash;
pub mod pf_core;
pub mod pf_core_catalog;
pub mod schema;
pub mod status;
pub mod validation;

pub use hash::{canonical_hash, canonical_json_bytes, canonical_json_string};
pub use pf_core::{
    compute_event_hash, compute_trace_hash, parse_contract_semantics_checked,
    resource_matches_pattern, validate_claim_class_overclaim, validate_contract_semantics_checked,
    validate_cross_tenant_safety, validate_denied_events_preserved,
    validate_observational_non_interference, validate_observational_non_interference_all_pairs,
    validate_direct_trace_action_semantics, validate_event_against_contract,
    validate_pfcore_certificate_semantics, validate_pfcore_trace_hash_chain,
    trace_safe_d, trace_safe_rd, event_safe_d, event_safe_rd,
    action_admissible_with_resource_pattern_d,
    validate_tenant_isolation, validate_trace_contracts, ContractSemanticsChecked, GENESIS_HASH,
};
pub use pf_core_catalog::{CAPABILITY_CATALOG, EFFECT_KINDS, ROLE_CAPABILITY_MAP};
pub use validation::{
    detect_artifact_type, validate_artifact, validate_semantics, ValidationError,
};
