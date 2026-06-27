import { canonicalHash } from "./hash.js";

export const GENESIS_HASH =
  "sha256:0000000000000000000000000000000000000000000000000000000000000000";

const LEAN_CLAIM_CLASSES = new Set(["LeanKernelChecked"]);

function stripDigestFields(
  data: Record<string, unknown>,
  extraKeys: string[],
): Record<string, unknown> {
  const payload = { ...data };
  for (const key of extraKeys) {
    delete payload[key];
  }
  delete payload.signature_or_digest;
  return payload;
}

export function computeEventHash(event: Record<string, unknown>): string {
  return canonicalHash(stripDigestFields(event, ["event_hash"]));
}

export function computeTraceHash(trace: Record<string, unknown>): string {
  return canonicalHash(stripDigestFields(trace, ["trace_hash"]));
}

function normalizeHash(value: string): string {
  const trimmed = value.trim();
  if (!trimmed.startsWith("sha256:") || trimmed.length !== 71) {
    throw new Error(`invalid hash ${value}`);
  }
  return trimmed;
}

export function validateClaimClassOverclaim(
  claimClass: string,
  proofRef?: unknown,
  leanProofChecked?: unknown,
): string | null {
  const hasProof =
    typeof proofRef === "string" && proofRef.trim().length > 0;
  if (LEAN_CLAIM_CLASSES.has(claimClass) && !hasProof) {
    return `ClaimClassOverclaim: claim_class ${JSON.stringify(claimClass)} exceeds available assurance`;
  }
  if (claimClass === "CertificateChecked") {
    return 'ClaimClassOverclaim: claim_class "CertificateChecked" exceeds available assurance';
  }
  if (claimClass === "LeanKernelChecked" && leanProofChecked !== true) {
    return "ClaimClassOverclaim: claim_class LeanKernelChecked requires lean_proof_checked=true";
  }
  return null;
}

export function validatePfcoreTraceHashChain(trace: Record<string, unknown>): string[] {
  const errors: string[] = [];
  const events = trace.events;
  if (!Array.isArray(events)) {
    return ["TraceInvalid: events must be an array"];
  }

  let previous = normalizeHash(GENESIS_HASH);
  for (let index = 0; index < events.length; index += 1) {
    const base = `events[${index}]`;
    const event = events[index];
    if (!event || typeof event !== "object" || Array.isArray(event)) {
      errors.push(`EventInvalid: ${base} must be an object`);
      continue;
    }
    const eventObj = event as Record<string, unknown>;
    try {
      const prevField = normalizeHash(String(eventObj.previous_event_hash ?? ""));
      if (prevField !== previous) {
        errors.push(
          `EventHashMismatch: previous_event_hash mismatch at ${base} (expected ${previous}, got ${prevField})`,
        );
      }
      const actualHash = normalizeHash(String(eventObj.event_hash ?? ""));
      const expectedHash = computeEventHash(eventObj);
      if (actualHash !== expectedHash) {
        errors.push(
          `EventHashMismatch: event_hash mismatch at ${base} (expected ${expectedHash}, got ${actualHash})`,
        );
      }
      previous = actualHash;
    } catch {
      errors.push(`EventHashMismatch: invalid event hash fields at ${base}`);
    }
  }

  if (trace.trace_hash !== undefined) {
    try {
      const actualTraceHash = normalizeHash(String(trace.trace_hash));
      const expectedTraceHash = computeTraceHash(trace);
      if (actualTraceHash !== expectedTraceHash) {
        errors.push(
          `TraceHashMismatch: trace_hash mismatch (expected ${expectedTraceHash}, got ${actualTraceHash})`,
        );
      }
    } catch {
      errors.push("TraceHashMismatch: invalid trace_hash");
    }
  }

  if (typeof trace.claim_class === "string") {
    const overclaim = validateClaimClassOverclaim(
      trace.claim_class,
      trace.proof_ref ?? trace.proof_term_ref,
      trace.lean_proof_checked,
    );
    if (overclaim) {
      errors.push(overclaim);
    }
  }

  return errors;
}

export function validatePfcoreCertificateSemantics(
  certificate: Record<string, unknown>,
): string[] {
  const errors: string[] = [];
  const claimClass = String(certificate.claim_class ?? "");
  const overclaim = validateClaimClassOverclaim(
    claimClass,
    certificate.proof_ref ?? certificate.proof_term_ref,
    certificate.lean_proof_checked,
  );
  if (overclaim) {
    errors.push(overclaim);
  }
  if (claimClass === "LeanKernelChecked") {
    if (certificate.lean_proof_checked !== true) {
      errors.push("root: claim_class LeanKernelChecked requires lean_proof_checked=true");
    }
    if (
      typeof certificate.proof_term_ref !== "string" ||
      certificate.proof_term_ref.trim().length === 0
    ) {
      errors.push(
        "root: claim_class LeanKernelChecked requires proof_term_ref (ClaimClassOverclaim)",
      );
    }
    const envHash = certificate.lean_environment_hash;
    if (typeof envHash !== "string" || !envHash.startsWith("sha256:")) {
      errors.push("root: claim_class LeanKernelChecked requires lean_environment_hash");
    }
    const build = certificate.lean_build_status;
    if (
      !build ||
      typeof build !== "object" ||
      Array.isArray(build) ||
      (build as Record<string, unknown>).ok !== true
    ) {
      errors.push("root: lean_proof_checked requires lean_build_status.ok=true");
    }
  }
  return errors;
}
