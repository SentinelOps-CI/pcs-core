import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { canonicalHash } from "../hash.js";
import { detectArtifactType } from "../artifact.js";
import { validateArtifact, ValidationError } from "../validate.js";

const examplesDir = join(dirname(fileURLToPath(import.meta.url)), "../../../../../examples");

function load(name: string): Record<string, unknown> {
  return JSON.parse(readFileSync(join(examplesDir, name), "utf8")) as Record<string, unknown>;
}

test("valid examples parse", () => {
  const files = readdirSync(examplesDir).filter((f) => f.endsWith(".valid.json"));
  for (const file of files) {
    const data = load(file);
    const type = detectArtifactType(data);
    assert.ok(type, `detect type for ${file}`);
    validateArtifact(data, type);
  }
});

test("invalid unknown status", () => {
  const data = load("invalid_unknown_status.json");
  assert.throws(() => validateArtifact(data, "RuntimeReceipt.v0"), ValidationError);
});

test("invalid missing assumption set", () => {
  const data = load("invalid_missing_assumption_set.json");
  assert.throws(() => validateArtifact(data, "ClaimArtifact.v0"), ValidationError);
});

test("invalid mismatched trace hash", () => {
  const data = load("invalid_mismatched_trace_hash.json");
  assert.throws(() => validateArtifact(data, "ScienceClaimBundle.v0"), ValidationError);
});

test("canonical hash stable", () => {
  const data = load("science_claim_bundle.valid.json");
  assert.equal(canonicalHash(data), canonicalHash(data));
});
