"""Fixed PCS and PF-Core Lean obligation kinds and theorem names."""

from __future__ import annotations

# PCS release-envelope family (lean/PCS/Theorems.lean).
PCS_OBLIGATION_KIND_THEOREM: dict[str, str] = {
    "CertificateMatchesRuntime": "admissible_release_has_matching_trace_hash",
    "VerificationAdmitsBundle": ("admissible_release_has_verified_input_hash_equal_to_bundle_hash"),
    "SignedBundleAdmissible": (
        "admissible_release_has_signed_input_hash_equal_to_verified_input_hash"
    ),
    "ToolTraceHashMatchesCertificate": "tool_trace_hash_matches_certificate",
    "ComputationWitnessHashAlignment": "witness_result_hashes_admissible",
    "ReleaseChainAdmissible": "concrete_release_chain_admissible_prop",
}

PCS_UNTRUSTED_OBLIGATION_KIND_THEOREM: dict[str, str] = {}

# PF-Core trace-safety family (lean/PFCore/Theorems.lean + Soundness.lean).
PF_CORE_OBLIGATION_KIND_THEOREM: dict[str, str] = {
    "HasCapabilityDeciderSound": "hasCapabilityD_sound",
    "ActionWithinTenantDeciderSound": "actionWithinTenantD_sound",
    "ActionAllowedDeciderSound": "actionAllowedD_sound",
    "EventSafeDeciderSound": "eventSafeD_sound",
    "TraceSafeEmpty": "traceSafe_empty",
    "TraceSafeCons": "traceSafe_cons",
    "TraceSafeDeciderSound": "traceSafeD_sound",
    "AllowedEventHasAllowedAction": "allowed_event_has_allowed_action",
    "EveryAllowedEventInSafeTraceIsAllowed": "every_allowed_event_in_safe_trace_is_allowed",
    "HandoffDoesNotExpandAuthority": "handoff_does_not_expand_authority",
    "SeqContractSatisfactionLeft": "seq_contract_satisfaction_left",
    "SeqContractSatisfactionRight": "seq_contract_satisfaction_right",
    "ConsPreservesTenantScope": "cons_preserves_tenant_scope",
    "TraceSafeAllowedEventTenantScoped": "traceSafe_allowed_event_tenant_scoped",
    "ContractPreDeciderSound": "contractPreD_sound",
    "ContractPostDeciderSound": "contractPostD_sound",
    "SatisfiesContractSpecDeciderSound": "satisfiesContractSpecD_sound",
    "TraceSatisfiesContractSpecsDeciderSound": "traceSatisfiesContractSpecsD_sound",
    "SafeExtensionPreservesTraceSafe": "safe_extension_preserves_trace_safe",
    "ContractInvariantPreservedBySafeExtension": "contract_invariant_preserved_by_safe_extension",
    "HandoffCompositionDoesNotExpandAuthority": "handoff_composition_does_not_expand_authority",
    "ComposedContractPreservesComponentInvariants": "composed_contract_preserves_component_invariants",
    "AlignedRoleCapabilityGranted": "aligned_role_capability_granted",
    "HandoffPreservesTraceSafe": "handoff_preserves_trace_safe",
    "TraceSafeImpliesTraceCrossTenantSafe": "traceSafe_implies_trace_cross_tenant_safe",
    "RuntimeRoleExpansionSubset": "runtime_role_expansion_subset",
    "StepStateFramePreserved": "stepState_frame_preserved",
    "TraceExtendsSafelyOfStep": "traceExtendsSafely_of_step",
    "SafeExtensionPreservesTraceSafeStrong": "safe_extension_preserves_trace_safe_strong",
    "EffectFramePreventsUndeclaredWrites": "effect_frame_prevents_undeclared_writes",
    "ContractRefinementPreservesTraceSafe": "contract_refinement_preserves_trace_safe",
    "HandoffPreservesTraceSafeStrong": "handoff_preserves_trace_safe_strong",
    "HandoffCompositionGlobal": "handoff_composition_global",
    "TraceSafeImpliesTenantIsolation": "traceSafe_implies_tenant_isolation",
    "ContractPreRoleAlignedCapability": "contractPre_role_aligned_capability",
}

PF_CORE_SOUNDNESS_THEOREMS = frozenset(
    {
        "hasCapabilityD_sound",
        "actionWithinTenantD_sound",
        "actionAllowedD_sound",
        "eventSafeD_sound",
        "traceSafe_empty",
        "traceSafe_cons",
        "traceSafeD_sound",
        "handoffSafeD_sound",
        "handoff_does_not_expand_authority",
        "capabilitySubsetD_sound",
        "sameTenantResourceD_sound",
        "resourcesSameTenantD_sound",
        "eventInD_sound",
        "eventTenantScopedD_sound",
        "traceTenantScopedD_sound",
        "actionHasEffectD_sound",
        "contractPreD_sound",
        "contractPostD_sound",
        "contractInvariantD_sound",
        "satisfiesContractSpecD_sound",
        "traceSatisfiesContractSpecsD_sound",
        "eventCrossTenantSafeD_sound",
        "traceCrossTenantSafeD_sound",
        "frameValidD_sound",
        "traceExtendsSafelyD_sound",
        "effectAllowedInFrameD_sound",
        "actionEffectsInFrameD_sound",
        "effectFrameAdmissibleD_sound",
        "tenantIsolationD_sound",
        "eventTenantIsolatedD_sound",
        "principalHasRoleD_sound",
    }
)

PF_CORE_THEOREM_CATALOG = (
    frozenset(PF_CORE_OBLIGATION_KIND_THEOREM.values()) | PF_CORE_SOUNDNESS_THEOREMS
)

# Concrete proof obligations emitted by pf_core_lean_codegen (LeanKernelChecked only).
PF_CORE_CONCRETE_PROOF_THEOREMS = frozenset(
    {
        "concrete_trace_safe",
        "concrete_trace_safe_prop",
        "concrete_allowed_events_allowed",
    }
)

PF_CORE_LEAN_KERNEL_THEOREM_CATALOG = PF_CORE_THEOREM_CATALOG | PF_CORE_CONCRETE_PROOF_THEOREMS

# Backward-compatible PCS aliases (Stage 1).
OBLIGATION_KIND_THEOREM = PCS_OBLIGATION_KIND_THEOREM
UNTRUSTED_OBLIGATION_KIND_THEOREM = PCS_UNTRUSTED_OBLIGATION_KIND_THEOREM
KNOWN_OBLIGATION_KINDS = frozenset(OBLIGATION_KIND_THEOREM.keys())
UNTRUSTED_OBLIGATION_KINDS = frozenset(UNTRUSTED_OBLIGATION_KIND_THEOREM.keys())
PCS_CONCRETE_PROOF_THEOREMS = frozenset(
    {
        "concrete_certificate_matches_runtime",
        "concrete_verification_admits_bundle",
        "concrete_signed_bundle_admissible",
        "concrete_release_chain_admissible",
        "concrete_release_chain_admissible_prop",
    }
)

LEAN_THEOREM_CATALOG = frozenset(OBLIGATION_KIND_THEOREM.values()) | PCS_CONCRETE_PROOF_THEOREMS
UNTRUSTED_LEAN_THEOREM_CATALOG = frozenset(UNTRUSTED_OBLIGATION_KIND_THEOREM.values())

LEAN_THEOREM_FAMILY = "Release-envelope consistency theorem family"
PF_CORE_LEAN_THEOREM_FAMILY = "PF-Core trace-safety theorem family"

PF_CORE_TRUSTED_LEAN_DIR = "lean/PFCore"

PF_CORE_FORBIDDEN_LEAN_TOKENS: tuple[str, ...] = ("sorry", "admit", "axiom", "unsafe")
