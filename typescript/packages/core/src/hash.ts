import { createHash } from "node:crypto";

const SIGNATURE_FIELD = "signature_or_digest";

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
  const payload = { ...data };
  delete payload[SIGNATURE_FIELD];
  return sortValue(payload) as Record<string, unknown>;
}

export function canonicalHash(data: Record<string, unknown>): string {
  const canonical = canonicalizeForHash(data);
  const bytes = Buffer.from(JSON.stringify(canonical), "utf8");
  const digest = createHash("sha256").update(bytes).digest("hex");
  return `sha256:${digest}`;
}
