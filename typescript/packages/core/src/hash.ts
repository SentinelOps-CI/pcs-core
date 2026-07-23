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

export function canonicalizeForHash(data: Record<string, unknown>): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (!HASH_EXCLUDED_FIELDS.has(key)) {
      payload[key] = value;
    }
  }
  return sortValue(payload) as Record<string, unknown>;
}

export function canonicalJsonBytes(data: Record<string, unknown>): Uint8Array {
  const canonical = canonicalizeForHash(data);
  return Buffer.from(JSON.stringify(canonical), "utf8");
}

export function canonicalHash(data: Record<string, unknown>): string {
  const digest = createHash("sha256").update(canonicalJsonBytes(data)).digest("hex");
  return `sha256:${digest}`;
}
