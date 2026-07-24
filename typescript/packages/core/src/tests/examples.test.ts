import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  CANONICALIZATION_VERSION,
  REJECTION_FLOAT_PROHIBITED,
  REJECTION_INTEGER_OUT_OF_RANGE,
  REJECTION_NEGATIVE_ZERO,
  SAFE_INTEGER_MAX,
  SAFE_INTEGER_MIN,
  CanonicalizationError,
  canonicalHash,
  canonicalHashLegacy,
  canonicalHashRelease,
  canonicalJsonBytes,
  tryCanonicalHashRelease,
} from "../hash.js";
import {
  canonicalEventJsonBytes,
  canonicalTraceJsonBytes,
  computeEventHash,
  computeTraceHash,
  validateClaimClassOverclaim,
  validateContractSemanticsChecked,
  validateCrossTenantSafety,
  validateDeniedEventsPreserved,
  validateDirectTraceActionSemantics,
  validatePfcoreCertificateSemantics,
  traceSafeD,
  traceSafeRD,
  validatePfcoreTraceHashChain,
  validateObservationalNonInterference,
  validateObservationalNonInterferenceAllPairs,
  validateTenantIsolation,
  validateEventSafeDenyClosed,
  validateObservedEffectsAgree,
  validateTraceContracts,
  resolveCertificateModeDefault,
  resolveToolMapping,
} from "../pfCore.js";
import {
  constructVaArtifact,
  validateVaSemantics,
  verifyAssuranceReport,
} from "../verifierAssurance.js";
import { detectArtifactType, validateArtifact, ValidationError, type ArtifactType } from "../validate.js";

const examplesDir = join(dirname(fileURLToPath(import.meta.url)), "../../../../../examples");
const vectorsDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../../python/tests/hash_vectors",
);
const pfCoreVectorsDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../../python/tests/hash_vectors/pf_core",
);
const pfCoreInvalidVectorsDir = join(pfCoreVectorsDir, "invalid");
const pfCoreInvalidExamplesDir = join(examplesDir, "pf-core-invalid");
const sharedVectorsDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../../test_vectors/hash",
);
const canonV1Dir = join(sharedVectorsDir, "canonical_json_v1");

function load(rel: string): Record<string, unknown> {
  return JSON.parse(readFileSync(join(examplesDir, rel), "utf8")) as Record<string, unknown>;
}

function walkJsonFiles(dir: string): string[] {
  const found: string[] = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      found.push(...walkJsonFiles(path));
    } else if (name.endsWith(".json")) {
      found.push(path);
    }
  }
  return found;
}

function validExampleFiles(): string[] {
  return walkJsonFiles(examplesDir).filter((path) => path.includes(".valid."));
}

test("benchmark ingest examples include artifact refs", () => {
  const ingestDir = join(examplesDir, "benchmark_ingest");
  for (const name of readdirSync(ingestDir)) {
    if (!name.endsWith(".pcs_bench_ingest.valid.json")) {
      continue;
    }
    const data = JSON.parse(
      readFileSync(join(ingestDir, name), "utf8"),
    ) as Record<string, unknown>;
    assert.equal(detectArtifactType(data), "PcsBenchIngest.v0", name);
    validateArtifact(data, "PcsBenchIngest.v0");
    const refs = data.artifact_refs;
    assert.ok(Array.isArray(refs) && refs.length > 0, `${name} must include artifact_refs`);
  }
});

test("PF-Core explicit artifact_type detection", () => {
  const cases: Array<[string, string]> = [
    ["pf-core-valid/tool_use_trace_compiled/pfcore_trace.json", "PFCoreTrace.v0"],
    ["pf-core-valid/assumption_declared/certificate.json", "PFCoreCertificate.v0"],
  ];
  for (const [rel, expected] of cases) {
    const data = JSON.parse(
      readFileSync(join(examplesDir, rel), "utf8"),
    ) as Record<string, unknown>;
    assert.equal(detectArtifactType(data), expected, rel);
  }
});

test("valid examples pass schema and semantic validation", () => {
  for (const path of validExampleFiles()) {
    const data = JSON.parse(readFileSync(path, "utf8")) as Record<string, unknown>;
    const rel = path.slice(examplesDir.length + 1).replace(/\\/g, "/");
    const type = detectArtifactType(data);
    assert.ok(type, `detect type for ${rel}`);
    validateArtifact(data, type);
  }
});

test("invalid unknown status", () => {
  assert.throws(() => validateArtifact(load("invalid_unknown_status.json"), "RuntimeReceipt.v0"));
});

test("invalid missing assumption set", () => {
  assert.throws(() => validateArtifact(load("invalid_missing_assumption_set.json")));
});

test("invalid mismatched trace hash", () => {
  assert.throws(() => validateArtifact(load("invalid_mismatched_trace_hash.json")));
});

test("invalid pcs bench ingest missing refs", () => {
  const data = load("invalid_pcs_bench_ingest_missing_refs.json");
  assert.throws(() => validateArtifact(data, "PcsBenchIngest.v0"));
});

test("invalid pcs bench ingest bad ref digest", () => {
  const data = load("invalid_pcs_bench_ingest_bad_ref_digest.json");
  assert.throws(() => validateArtifact(data, "PcsBenchIngest.v0"));
});

test("invalid pcs bench ingest zero commit", () => {
  const data = load("invalid_pcs_bench_ingest_zero_commit.json");
  assert.throws(() => validateArtifact(data, "PcsBenchIngest.v0"));
});

test("invalid pcs bench ingest empty runs", () => {
  const data = load("invalid_pcs_bench_ingest_empty_runs.json");
  assert.throws(() => validateArtifact(data, "PcsBenchIngest.v0"));
});

test("invalid pcs bench ingest path only", () => {
  const data = load("invalid_pcs_bench_ingest_path_only.json");
  assert.throws(() => validateArtifact(data, "PcsBenchIngest.v0"));
});

test("invalid zero source commit", () => {
  assert.throws(() =>
    validateArtifact(load("invalid_zero_source_commit.release.json"), "RuntimeReceipt.v0"),
  );
});

test("labtrust invalid singular runtime receipt bundle", () => {
  assert.throws(() =>
    validateArtifact(
      load("labtrust/invalid_singular_runtime_receipt_bundle.json"),
      "ScienceClaimBundle.v0",
    ),
  );
});

test("labtrust invalid signed schema_version artifact name", () => {
  assert.throws(() =>
    validateArtifact(
      load("labtrust/invalid_signed_schema_version_artifact_name.json"),
      "SignedScienceClaimBundle.v0",
    ),
  );
});

test("labtrust invalid failed verification result", () => {
  assert.throws(() => validateArtifact(load("labtrust/invalid_failed_verification_result.json")));
});

test("labtrust invalid missing trace certificate", () => {
  assert.throws(() =>
    validateArtifact(load("labtrust/invalid_missing_trace_certificate.json")),
  );
});

test("computation artifacts detect and validate", () => {
  for (const rel of [
    "dataset_receipt.valid.json",
    "environment_receipt.valid.json",
    "computation_run_receipt.valid.json",
    "result_artifact.valid.json",
    "computation_witness.valid.json",
  ]) {
    const data = load(rel);
    const type = detectArtifactType(data);
    assert.ok(type, `detect type for ${rel}`);
    validateArtifact(data, type);
  }
});

test("canonical hash stable", () => {
  const data = load("science_claim_bundle.certified.valid.json");
  assert.equal(canonicalHash(data), canonicalHash(data));
});

test("hash vectors match frozen fixtures", () => {
  for (const artifact of [
    "RuntimeReceipt.v0",
    "TraceCertificate.v0",
    "ScienceClaimBundle.v0",
    "SignedScienceClaimBundle.v0",
  ]) {
    const dir = join(vectorsDir, artifact);
    const data = JSON.parse(readFileSync(join(dir, "input.json"), "utf8")) as Record<
      string,
      unknown
    >;
    const expectedCanonical = readFileSync(join(dir, "canonical.txt"), "utf8").trim();
    const expectedDigest = readFileSync(join(dir, "digest.txt"), "utf8").trim();
    assert.equal(Buffer.from(canonicalJsonBytes(data)).toString("utf8"), expectedCanonical);
    assert.equal(canonicalHash(data), expectedDigest);
  }
});

test("pf-core hash vectors match frozen fixtures", () => {
  for (const artifact of ["PFCoreEvent.v0", "PFCoreTrace.v0"]) {
    const dir = join(pfCoreVectorsDir, artifact);
    const data = JSON.parse(readFileSync(join(dir, "input.json"), "utf8")) as Record<
      string,
      unknown
    >;
    const expectedCanonical = readFileSync(join(dir, "canonical.txt"), "utf8").trim();
    const expectedDigest = readFileSync(join(dir, "digest.txt"), "utf8").trim();
    const canonicalBytes =
      artifact === "PFCoreEvent.v0"
        ? canonicalEventJsonBytes(data)
        : canonicalTraceJsonBytes(data);
    assert.equal(Buffer.from(canonicalBytes).toString("utf8"), expectedCanonical);
    if (artifact === "PFCoreEvent.v0") {
      assert.equal(computeEventHash(data), expectedDigest);
    } else {
      assert.equal(computeTraceHash(data), expectedDigest);
    }
  }
});

test("pf-core negative hash vectors parity", () => {
  const trace = JSON.parse(
    readFileSync(join(pfCoreInvalidVectorsDir, "trace_hash_chain_break.json"), "utf8"),
  ) as Record<string, unknown>;
  const hashErrors = validatePfcoreTraceHashChain(trace);
  assert.ok(hashErrors.some((err) => err.includes("EventHashMismatch")));

  const overclaimTrace = JSON.parse(
    readFileSync(join(pfCoreInvalidVectorsDir, "claim_class_overclaim_trace.json"), "utf8"),
  ) as Record<string, unknown>;
  const overclaimErrors = validatePfcoreTraceHashChain(overclaimTrace);
  assert.ok(overclaimErrors.some((err) => err.includes("ClaimClassOverclaim")));

  const traceMismatch = JSON.parse(
    readFileSync(join(pfCoreInvalidVectorsDir, "trace_hash_mismatch.json"), "utf8"),
  ) as Record<string, unknown>;
  const traceMismatchErrors = validatePfcoreTraceHashChain(traceMismatch);
  assert.ok(traceMismatchErrors.some((err) => err.includes("TraceHashMismatch")));

  const prevMismatch = JSON.parse(
    readFileSync(join(pfCoreInvalidVectorsDir, "previous_event_hash_mismatch.json"), "utf8"),
  ) as Record<string, unknown>;
  const prevMismatchErrors = validatePfcoreTraceHashChain(prevMismatch);
  assert.ok(prevMismatchErrors.some((err) => err.includes("EventHashMismatch")));

  const crossTenant = JSON.parse(
    readFileSync(join(pfCoreInvalidVectorsDir, "cross_tenant_leak.json"), "utf8"),
  ) as Record<string, unknown>;
  const tenantErrors = validateTenantIsolation(crossTenant);
  assert.ok(tenantErrors.some((err) => err.includes("TenantIsolation")));
  const crossTenantErrors = validateCrossTenantSafety(crossTenant);
  assert.ok(crossTenantErrors.some((err) => err.includes("CrossTenantSafe")));

  const allowedTrace = JSON.parse(
    readFileSync(
      join(examplesDir, "pf-core-valid/file_read_allowed/trace.json"),
      "utf8",
    ),
  ) as Record<string, unknown>;
  assert.deepEqual(validateCrossTenantSafety(allowedTrace), []);
  assert.deepEqual(validateTenantIsolation(allowedTrace), []);
  const events = allowedTrace.events as Record<string, unknown>[];
  const tenant = String((events[0]?.principal as Record<string, unknown>)?.tenant ?? "");
  assert.deepEqual(validateObservationalNonInterference(allowedTrace, tenant, "other-tenant"), []);
  assert.deepEqual(validateObservationalNonInterferenceAllPairs(allowedTrace), []);

  const contractDir = join(pfCoreInvalidVectorsDir, "contract_capability_missing");
  const contractTrace = JSON.parse(
    readFileSync(join(contractDir, "trace.json"), "utf8"),
  ) as Record<string, unknown>;
  const contract = JSON.parse(
    readFileSync(join(contractDir, "contract.json"), "utf8"),
  ) as Record<string, unknown>;
  const contractId = String(contract.contract_id ?? "");
  const contractErrors = validateTraceContracts(contractTrace, { [contractId]: contract });
  assert.ok(contractErrors.some((err) => err.includes("ContractCapabilityRequired")));

  const deniedDir = join(pfCoreInvalidVectorsDir, "denied_event_dropped");
  const toolUse = JSON.parse(
    readFileSync(join(deniedDir, "tool_use_trace.json"), "utf8"),
  ) as Record<string, unknown>;
  const pfcore = JSON.parse(
    readFileSync(join(deniedDir, "pfcore_trace.json"), "utf8"),
  ) as Record<string, unknown>;
  const deniedErrors = validateDeniedEventsPreserved(toolUse, pfcore);
  assert.ok(deniedErrors.some((err) => err.includes("DroppedDeniedEvent")));

  assert.ok(
    validateClaimClassOverclaim("LeanKernelChecked", undefined, undefined)?.includes(
      "ClaimClassOverclaim",
    ),
  );
});

test("pf-core direct-trace semantics invalid vectors", () => {
  const cases: Array<[string, string]> = [
    ["unknown_direct_trace_effect/trace.json", "UnknownEffect"],
    ["capability_effect_mismatch/trace.json", "CapabilityEffectMismatch"],
    ["unknown_direct_trace_capability/trace.json", "UnknownCapability"],
  ];
  for (const [relative, needle] of cases) {
    const trace = JSON.parse(
      readFileSync(join(pfCoreInvalidExamplesDir, relative), "utf8"),
    ) as Record<string, unknown>;
    const errors = validateDirectTraceActionSemantics(trace);
    assert.ok(
      errors.some((err) => err.includes(needle)),
      `${relative}: expected ${needle} in ${errors.join("; ")}`,
    );
  }
});


test("pf-core traceSafeRD decider parity", () => {
  const trace = JSON.parse(
    readFileSync(join(examplesDir, "pf-core-valid/tool_use_trace_compiled/pfcore_trace.json"), "utf8"),
  ) as Record<string, unknown>;
  const events = trace.events as Record<string, unknown>[];
  assert.equal(traceSafeD(events), true);
  assert.equal(traceSafeRD(events), true);
  const bad = JSON.parse(
    readFileSync(join(pfCoreInvalidExamplesDir, "resource_scope_violation/trace.json"), "utf8"),
  ) as Record<string, unknown>;
  const badEvents = bad.events as Record<string, unknown>[];
  // A11: base TraceSafe holds; refined TraceSafeR rejects out-of-pattern URI.
  assert.equal(traceSafeD(badEvents), true);
  assert.equal(traceSafeRD(badEvents), false);
});

test("pf-core resource scope violation vector", () => {
  const trace = JSON.parse(
    readFileSync(join(pfCoreInvalidExamplesDir, "resource_scope_violation/trace.json"), "utf8"),
  ) as Record<string, unknown>;
  const errors = validatePfcoreTraceHashChain(trace);
  assert.ok(errors.some((err) => err.includes("ResourceScopeViolation")));
});

test("pf-core contract_semantics_checked resource obligations", () => {
  const missingLean = {
    claim_class: "LeanKernelChecked",
    lean_proof_checked: true,
    default_contract_ref: "trace-safe",
    contract_semantics_checked: {
      lean: [] as string[],
      runtime: ["resource_pattern_scope"],
    },
  };
  const missingErrors = validateContractSemanticsChecked(missingLean);
  assert.ok(
    missingErrors.some((err) => err.includes("resource_within_capability_pattern")),
    missingErrors.join("; "),
  );

  const ok = {
    claim_class: "LeanKernelChecked",
    lean_proof_checked: true,
    default_contract_ref: "trace-safe",
    contract_semantics_checked: {
      lean: ["resource_within_capability_pattern"],
      runtime: ["resource_pattern_scope"],
    },
  };
  assert.deepEqual(validateContractSemanticsChecked(ok), []);
});

test("pf-core audit invalid vectors parity", () => {
  const traceCases: Array<[string, string]> = [
    ["lean_kernel_checked_on_trace/trace.json", "ClaimClassOverclaim"],
    ["lean_kernel_checked_without_proof_ref/trace.json", "ClaimClassOverclaim"],
  ];
  for (const [relative, needle] of traceCases) {
    const trace = JSON.parse(
      readFileSync(join(pfCoreInvalidExamplesDir, relative), "utf8"),
    ) as Record<string, unknown>;
    const errors = validatePfcoreTraceHashChain(trace);
    assert.ok(errors.some((err) => err.includes(needle)), `${relative}: ${errors.join("; ")}`);
  }

  const certificateCases: Array<[string, string]> = [
    ["lean_kernel_checked_without_proof_term_hash/certificate.json", "proof_term_hash"],
    ["lean_kernel_checked_without_proof_term_ref/certificate.json", "proof_term_ref"],
    ["lean_kernel_checked_with_skipped_build/certificate.json", "lean_build_status"],
    [
      "certificate_mode_effectframecertificate_missing_obligations/certificate.json",
      "certificate_mode obligations",
    ],
    [
      "certificate_mode_contractcheckedcertificate_missing_contract_file/certificate.json",
      "ContractCheckedCertificate cannot claim lean_proof_checked",
    ],
  ];
  for (const [relative, needle] of certificateCases) {
    const certificate = JSON.parse(
      readFileSync(join(pfCoreInvalidExamplesDir, relative), "utf8"),
    ) as Record<string, unknown>;
    const errors = validatePfcoreCertificateSemantics(certificate);
    assert.ok(errors.some((err) => err.includes(needle)), `${relative}: ${errors.join("; ")}`);
  }
});

test("pf-core generated tool_map parity", () => {
  const [capId, effectKind, pattern] = resolveToolMapping("filesystem.read", "filesystem");
  assert.equal(capId, "cap:file-read");
  assert.equal(effectKind, "file.read");
  assert.equal(pattern, "/data/*");
  assert.throws(() => resolveToolMapping("unknown.tool", "misc"));
  const tracePath = join(examplesDir, "pf-core-valid/tool_use_trace_compiled/pfcore_trace.json");
  const trace = JSON.parse(readFileSync(tracePath, "utf8")) as Record<string, unknown>;
  assert.equal(resolveCertificateModeDefault({}, tracePath, trace), "TraceSafeRCertificate");
  const catalogTrace = {
    workflow_id: "agent_tool_use.safety_v0",
  } as Record<string, unknown>;
  assert.equal(
    resolveCertificateModeDefault({}, undefined, catalogTrace),
    "TraceSafeRCertificate",
  );
});

test("shared hash vectors match test_vectors/hash fixtures", () => {
  for (const fileName of readdirSync(sharedVectorsDir)) {
    if (!fileName.endsWith(".vector.json")) {
      continue;
    }
    const vector = JSON.parse(
      readFileSync(join(sharedVectorsDir, fileName), "utf8"),
    ) as {
      artifact_type: string;
      input?: string;
      input_file?: string;
      expected_digest: string;
      canonical_json: string;
    };
    const inputPath = (vector.input ?? vector.input_file ?? "").replace(/\\/g, "/");
    const data = load(inputPath.replace(/^examples\//, ""));
    assert.equal(Buffer.from(canonicalJsonBytes(data)).toString("utf8"), vector.canonical_json);
    assert.equal(canonicalHash(data), vector.expected_digest);
  }
});

test("validateEventSafeDenyClosed rejects deny writes", () => {
  const allowed = load("pf-core-valid/file_read_allowed/trace.json") as Record<string, unknown>;
  assert.deepEqual(validateEventSafeDenyClosed(allowed), []);
  const events = allowed.events as Array<Record<string, unknown>>;
  const event = events[0];
  event.decision = "deny";
  (event.action as Record<string, unknown>).writes = [{ uri: "file:///tmp/x", tenant: "t" }];
  (event.action as Record<string, unknown>).effects = [{ effect_kind: "file.write" }];
  const errors = validateEventSafeDenyClosed(allowed);
  assert.ok(errors.some((e) => e.includes("EventSafeDenyClosed")));
});

test("validateObservedEffectsAgree parity cases", () => {
  const action = {
    effects: [{ effect_kind: "file.read" }],
    reads: [{ uri: "file:///a", tenant: "t" }],
    writes: [],
  };
  assert.deepEqual(
    validateObservedEffectsAgree(action, [
      { kind: "file.read", resource: { uri: "file:///a" } },
    ]),
    [],
  );
  assert.ok(validateObservedEffectsAgree(action, [{ kind: "file.write" }]).length > 0);
});

test("property digests have sha256 shape", () => {
  // Lightweight property loop (fast-check optional; avoid hard dep for offline/TLS-restricted installs).
  for (let i = 0; i < 32; i += 1) {
    const payload = { n: i, blob: "x".repeat(i % 17) };
    const digest = canonicalHash(payload);
    assert.ok(digest.startsWith("sha256:"));
    assert.equal(digest.length, 71);
  }
});

test("canonicalHashLegacy aliases canonicalHash", () => {
  const payload = { schema_version: "v0", artifact_type: "CanonicalProbe.v0", n: 1 };
  assert.equal(canonicalHashLegacy(payload), canonicalHash(payload));
});

test("canonicalHashRelease enforces number policy with normalized codes", () => {
  const safe = {
    schema_version: "v0",
    artifact_type: "CanonicalProbe.v0",
    lo: SAFE_INTEGER_MIN,
    hi: SAFE_INTEGER_MAX,
  };
  assert.equal(canonicalHashRelease(safe), canonicalHashLegacy(safe));

  assert.throws(
    () => canonicalHashRelease({ x: 1.5 }),
    (err: unknown) =>
      err instanceof CanonicalizationError && err.code === REJECTION_FLOAT_PROHIBITED,
  );
  assert.throws(
    () => canonicalHashRelease({ x: SAFE_INTEGER_MAX + 1 }),
    (err: unknown) =>
      err instanceof CanonicalizationError && err.code === REJECTION_INTEGER_OUT_OF_RANGE,
  );
  assert.throws(
    () => canonicalHashRelease({ x: SAFE_INTEGER_MIN - 1 }),
    (err: unknown) =>
      err instanceof CanonicalizationError && err.code === REJECTION_INTEGER_OUT_OF_RANGE,
  );
  assert.throws(
    () => canonicalHashRelease({ x: -0 }),
    (err: unknown) =>
      err instanceof CanonicalizationError && err.code === REJECTION_NEGATIVE_ZERO,
  );
  assert.equal(tryCanonicalHashRelease({ x: 1.5 }).rejection, REJECTION_FLOAT_PROHIBITED);
});

test("canonical_json_v1 accept and release-reject vectors", () => {
  const catalog = JSON.parse(readFileSync(join(canonV1Dir, "vectors.json"), "utf8")) as {
    canonicalization_version: string;
    cases: Array<{ case_id: string; expected_digest: string; canonical_json: string }>;
    release_reject_cases: Array<{
      case_id: string;
      expected_rejection: string;
      legacy_digest: string;
    }>;
  };
  assert.equal(catalog.canonicalization_version, CANONICALIZATION_VERSION);
  for (const caseRow of catalog.cases) {
    const data = JSON.parse(
      readFileSync(join(canonV1Dir, caseRow.case_id, "input.json"), "utf8"),
    ) as Record<string, unknown>;
    assert.equal(
      Buffer.from(canonicalJsonBytes(data)).toString("utf8"),
      caseRow.canonical_json,
      caseRow.case_id,
    );
    const digest = canonicalHashLegacy(data);
    assert.equal(digest, caseRow.expected_digest, caseRow.case_id);
    assert.equal(canonicalHashRelease(data), digest, caseRow.case_id);
  }
  for (const caseRow of catalog.release_reject_cases) {
    const data = JSON.parse(
      readFileSync(join(canonV1Dir, caseRow.case_id, "input.json"), "utf8"),
    ) as Record<string, unknown>;
    const result = tryCanonicalHashRelease(data);
    assert.equal(result.rejection, caseRow.expected_rejection, caseRow.case_id);
    // Legacy digests for float/-0 inputs can differ under ECMAScript JSON.stringify;
    // release mode must still share the normalized rejection code.
    assert.ok(canonicalHashLegacy(data).startsWith("sha256:"), caseRow.case_id);
  }
});

test("verifier assurance valid fixtures pass semantics", () => {
  const cases: Array<[string, string]> = [
    ["verifier_assurance/valid/profile_basic/profile.json", "VerifierProfile.v1"],
    ["verifier_assurance/valid/result_accept/result.json", "VerificationResult.v1"],
    ["verifier_assurance/valid/reward_scalar/reward.json", "RewardEvidenceEnvelope.v1"],
    ["verifier_assurance/valid/campaign_basic/campaign.json", "OptimizationCampaignManifest.v1"],
    ["verifier_assurance/valid/adjudication_basic/adjudication.json", "AdjudicationRecord.v1"],
    ["verifier_assurance/valid/report_rebuild/report.json", "VerifierAssuranceReport.v1"],
  ];
  for (const [rel, expected] of cases) {
    const data = load(rel);
    assert.equal(detectArtifactType(data), expected, rel);
    assert.deepEqual(validateVaSemantics(data, expected), []);
    validateArtifact(data, expected as ArtifactType);
  }
});

test("verifier assurance invalid fixtures emit expected codes", () => {
  const cases: Array<[string, string]> = [
    ["timeout_accept", "FailClosedDecision"],
    ["accept_mandatory_failure", "AcceptWithMandatoryFailure"],
    ["identical_normalization_digests", "IdenticalNormalizationDigests"],
    ["reward_total_mismatch", "RewardCompositionMismatch"],
    ["revoked_profile_active_reward", "RevokedProfileGate"],
    ["missing_rationale_commitment", "RationaleCommitment"],
    ["short_source_commit", "InvalidSourceCommit"],
    ["release_grade_no_adjudication", "ReleaseGradeAdjudication"],
    ["optimization_gap_missing_cohort", "OptimizationGapCohorts"],
    ["cohort_missing_access", "CohortAccessClass"],
    ["cohort_count_mismatch", "CohortCountMismatch"],
    ["excluded_items_invisible", "ExcludedItemsVisible"],
    ["missing_ci_method", "CIMethodsDeclared"],
    ["indeterminate_misclassification", "IndeterminateMisclassification"],
    ["active_reward_unresolved", "ActiveRewardUnresolvedClaims"],
  ];
  for (const [dir, code] of cases) {
    const manifest = load(`verifier_assurance/invalid/${dir}/manifest.json`);
    const artifactFile = String(manifest.artifact_file ?? "artifact.json");
    const artifactType = String(manifest.artifact_type);
    const data = load(`verifier_assurance/invalid/${dir}/${artifactFile}`);
    const issues = validateVaSemantics(data, artifactType);
    assert.ok(
      issues.some((i) => i.code === code),
      `${dir}: expected ${code}, got ${JSON.stringify(issues)}`,
    );
  }
});

test("verifier assurance verify report digest parity", () => {
  const report = load("verifier_assurance/valid/report_rebuild/report.json");
  assert.deepEqual(verifyAssuranceReport(report), []);
  const tampered = { ...report, report_id: "tampered-id" };
  const issues = verifyAssuranceReport(tampered);
  assert.ok(issues.some((i) => i.code === "ReportDigestMismatch"), JSON.stringify(issues));
});

test("verifier assurance constructor retains unknown fields", () => {
  assert.throws(() => constructVaArtifact("VerifierProfile.v1", {}));
  const fields: Record<string, unknown> = {
    schema_version: "v1",
    artifact_type: "VerifierProfile.v1",
    verifier_profile_id: "vp",
    created_at: "2026-07-24T00:00:00Z",
    producer: "pcs-core",
    producer_version: "0.1.0",
    source_repo: "https://example.invalid",
    source_commit: "e068794683959c52a19594a6d271dd5e69f3c999",
    implementation: {},
    configuration: {},
    mechanism: {},
    claim_surface: {},
    applicability: {},
    assumptions: [],
    known_blind_spots: [],
    integrity: { canonicalization_version: "v1", artifact_digest: "sha256:" + "a".repeat(64) },
    extra_field: true,
  };
  const built = constructVaArtifact("VerifierProfile.v1", fields);
  assert.equal(built.extra_field, true);
});
