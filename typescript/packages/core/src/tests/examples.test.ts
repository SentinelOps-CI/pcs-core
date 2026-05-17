import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { canonicalHash, canonicalJsonBytes } from "../hash.js";
import { detectArtifactType, validateArtifact, ValidationError } from "../validate.js";

const examplesDir = join(dirname(fileURLToPath(import.meta.url)), "../../../../../examples");
const vectorsDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../../python/tests/hash_vectors",
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
