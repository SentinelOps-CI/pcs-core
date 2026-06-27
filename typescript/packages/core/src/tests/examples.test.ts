import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { canonicalHash, canonicalJsonBytes } from "../hash.js";
import {
  canonicalEventJsonBytes,
  canonicalTraceJsonBytes,
  computeEventHash,
  computeTraceHash,
  validateClaimClassOverclaim,
  validateDeniedEventsPreserved,
  validatePfcoreTraceHashChain,
  validateTenantIsolation,
  validateTraceContracts,
} from "../pfCore.js";
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
const sharedVectorsDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../../test_vectors/hash",
);

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
    const inputPath = vector.input ?? vector.input_file ?? "";
    const data = load(inputPath.replace(/^examples\//, ""));
    assert.equal(Buffer.from(canonicalJsonBytes(data)).toString("utf8"), vector.canonical_json);
    assert.equal(canonicalHash(data), vector.expected_digest);
  }
});
