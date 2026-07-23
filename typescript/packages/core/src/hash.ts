import { createHash } from "node:crypto";

/** v0 compatibility field: integrity digest historically named like a signature. */
export const SIGNATURE_FIELD = "signature_or_digest";
/** v1 separated content digest. */
export const ARTIFACT_DIGEST_FIELD = "artifact_digest";
/** v1 cryptographic signature object. */
export const SIGNATURE_OBJECT_FIELD = "signature";

export const HASH_EXCLUDED_FIELDS = new Set([
  SIGNATURE_FIELD,
  ARTIFACT_DIGEST_FIELD,
  SIGNATURE_OBJECT_FIELD,
]);

/** PCS Canonical JSON algorithm version. */
export const CANONICALIZATION_VERSION = "v1";

export const SAFE_INTEGER_MIN = -9007199254740991;
export const SAFE_INTEGER_MAX = 9007199254740991;

/** Normalized rejection codes shared with Python and Rust release hashing. */
export const REJECTION_FLOAT_PROHIBITED = "float_prohibited";
export const REJECTION_INTEGER_OUT_OF_RANGE = "integer_out_of_range";
export const REJECTION_NEGATIVE_ZERO = "negative_zero";

export class CanonicalizationError extends Error {
  readonly code: string;
  readonly path: string;

  constructor(code: string, message: string, path = "$") {
    super(message);
    this.name = "CanonicalizationError";
    this.code = code;
    this.path = path;
  }
}

export function isZeroSourceCommit(commit: string): boolean {
  const trimmed = commit.trim();
  return trimmed.length > 0 && /^0+$/.test(trimmed);
}

export function domainSeparatedSigningMessage(args: {
  artifactType: string;
  schemaVersion: string;
  artifactDigest: string;
}): string {
  const { artifactType, schemaVersion, artifactDigest } = args;
  if (!artifactType || artifactType.includes(":")) {
    throw new Error(`invalid artifact_type for domain separation: ${artifactType}`);
  }
  if (!schemaVersion || schemaVersion.includes(":")) {
    throw new Error(`invalid schema_version for domain separation: ${schemaVersion}`);
  }
  if (!artifactDigest.startsWith("sha256:") || artifactDigest.length !== 71) {
    throw new Error(`invalid artifact_digest for domain separation: ${artifactDigest}`);
  }
  return `PCS:${artifactType}:${schemaVersion}:${artifactDigest}`;
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortValue);
  }
  if (value !== null && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj).sort();
    const sorted: Record<string, unknown> = {};
    for (const key of keys) {
      sorted[key] = sortValue(obj[key]);
    }
    return sorted;
  }
  return value;
}

/** Enforce Canonical JSON v1 number policy (strict / release hashing). */
export function assertCanonicalNumberPolicy(value: unknown, path = "$"): void {
  if (typeof value === "boolean" || value === null || typeof value === "string") {
    return;
  }
  if (typeof value === "number") {
    if (Object.is(value, -0)) {
      throw new CanonicalizationError(
        REJECTION_NEGATIVE_ZERO,
        `${path}: negative zero is prohibited under Canonical JSON v1`,
        path,
      );
    }
    if (!Number.isInteger(value)) {
      throw new CanonicalizationError(
        REJECTION_FLOAT_PROHIBITED,
        `${path}: float values are prohibited under Canonical JSON v1; use a normalized decimal string instead`,
        path,
      );
    }
    if (!Number.isSafeInteger(value)) {
      throw new CanonicalizationError(
        REJECTION_INTEGER_OUT_OF_RANGE,
        `${path}: integer ${value} outside safe-integer range [${SAFE_INTEGER_MIN}, ${SAFE_INTEGER_MAX}]`,
        path,
      );
    }
    return;
  }
  if (typeof value === "bigint") {
    if (value < BigInt(SAFE_INTEGER_MIN) || value > BigInt(SAFE_INTEGER_MAX)) {
      throw new CanonicalizationError(
        REJECTION_INTEGER_OUT_OF_RANGE,
        `${path}: integer ${value.toString()} outside safe-integer range [${SAFE_INTEGER_MIN}, ${SAFE_INTEGER_MAX}]`,
        path,
      );
    }
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((child, index) => {
      assertCanonicalNumberPolicy(child, `${path}[${index}]`);
    });
    return;
  }
  if (typeof value === "object") {
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      assertCanonicalNumberPolicy(child, `${path}.${key}`);
    }
  }
}

export function canonicalizeForHash(
  data: Record<string, unknown>,
  options: { enforceNumberPolicy?: boolean } = {},
): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (!HASH_EXCLUDED_FIELDS.has(key)) {
      payload[key] = value;
    }
  }
  if (options.enforceNumberPolicy) {
    assertCanonicalNumberPolicy(payload);
  }
  return sortValue(payload) as Record<string, unknown>;
}

export function canonicalJsonBytes(
  data: Record<string, unknown>,
  options: { enforceNumberPolicy?: boolean } = {},
): Uint8Array {
  const canonical = canonicalizeForHash(data, options);
  return Buffer.from(JSON.stringify(canonical), "utf8");
}

export function canonicalHash(
  data: Record<string, unknown>,
  options: { enforceNumberPolicy?: boolean } = {},
): string {
  const digest = createHash("sha256")
    .update(canonicalJsonBytes(data, options))
    .digest("hex");
  return `sha256:${digest}`;
}

/** Hash without the strict number policy (Phase 0 / legacy digest compatibility). */
export function canonicalHashLegacy(data: Record<string, unknown>): string {
  return canonicalHash(data, { enforceNumberPolicy: false });
}

/** Hash with the strict number policy always enforced (release integrity envelopes). */
export function canonicalHashRelease(data: Record<string, unknown>): string {
  return canonicalHash(data, { enforceNumberPolicy: true });
}

/** Return `{ digest }` or `{ rejection }` for cross-language vectors. */
export function tryCanonicalHashRelease(
  data: Record<string, unknown>,
): { digest: string; rejection?: undefined } | { digest?: undefined; rejection: string } {
  try {
    return { digest: canonicalHashRelease(data) };
  } catch (err) {
    if (err instanceof CanonicalizationError) {
      return { rejection: err.code };
    }
    throw err;
  }
}
