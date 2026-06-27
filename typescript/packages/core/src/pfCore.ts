import { canonicalHash, canonicalJsonBytes } from "./hash.js";

export const GENESIS_HASH =
  "sha256:0000000000000000000000000000000000000000000000000000000000000000";

const TRACE_CLAIM_CLASSES = new Set([
  "SchemaValidated",
  "RuntimeChecked",
  "ReplayValidated",
  "AssumptionDeclared",
  "OutOfScope",
]);

const CERTIFICATE_CLAIM_CLASSES = new Set([
  "SchemaValidated",
  "RuntimeChecked",
  "CertificateChecked",
  "LeanKernelChecked",
  "ReplayValidated",
  "AssumptionDeclared",
  "OutOfScope",
]);

const LEAN_CLAIM_CLASSES = new Set(["LeanKernelChecked"]);

const CONCRETE_PROOF_OBLIGATIONS = new Set([
  "concrete_trace_safe",
  "concrete_trace_safe_prop",
  "concrete_allowed_events_allowed",
]);

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

export function canonicalEventJsonBytes(event: Record<string, unknown>): Uint8Array {
  return canonicalJsonBytes(stripDigestFields(event, ["event_hash"]));
}

export function canonicalTraceJsonBytes(trace: Record<string, unknown>): Uint8Array {
  return canonicalJsonBytes(stripDigestFields(trace, ["trace_hash"]));
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

export function validateTraceClaimClassOverclaim(claimClass: string): string | null {
  if (!TRACE_CLAIM_CLASSES.has(claimClass)) {
    if (claimClass === "LeanKernelChecked" || claimClass === "CertificateChecked") {
      return `ClaimClassOverclaim: claim_class ${JSON.stringify(claimClass)} is not valid on PFCoreTrace.v0`;
    }
    return `ClaimClassOverclaim: invalid claim_class ${JSON.stringify(claimClass)} for trace`;
  }
  return null;
}

export function validateCertificateClaimClassOverclaim(
  claimClass: string,
  proofRef?: unknown,
  leanProofChecked?: unknown,
): string | null {
  if (!CERTIFICATE_CLAIM_CLASSES.has(claimClass)) {
    return `ClaimClassOverclaim: invalid claim_class ${JSON.stringify(claimClass)} for certificate`;
  }
  const hasProof =
    typeof proofRef === "string" && proofRef.trim().length > 0;
  if (LEAN_CLAIM_CLASSES.has(claimClass) && !hasProof) {
    return `ClaimClassOverclaim: claim_class ${JSON.stringify(claimClass)} exceeds available assurance`;
  }
  if (claimClass === "LeanKernelChecked" && leanProofChecked !== true) {
    return "ClaimClassOverclaim: claim_class LeanKernelChecked requires lean_proof_checked=true";
  }
  return null;
}

export function validateClaimClassOverclaim(
  claimClass: string,
  proofRef?: unknown,
  leanProofChecked?: unknown,
): string | null {
  return validateCertificateClaimClassOverclaim(claimClass, proofRef, leanProofChecked);
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
    const overclaim = validateTraceClaimClassOverclaim(trace.claim_class);
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
  const overclaim = validateCertificateClaimClassOverclaim(
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
    const proofTermHash = certificate.proof_term_hash;
    if (typeof proofTermHash !== "string" || !proofTermHash.startsWith("sha256:")) {
      errors.push("root: claim_class LeanKernelChecked requires proof_term_hash");
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
    if (certificate.lean_proof_checked === true) {
      const obligations = certificate.obligations;
      const passed = new Set<string>();
      if (Array.isArray(obligations)) {
        for (const item of obligations) {
          if (
            item &&
            typeof item === "object" &&
            !Array.isArray(item) &&
            (item as Record<string, unknown>).passed === true &&
            typeof (item as Record<string, unknown>).theorem === "string"
          ) {
            passed.add(String((item as Record<string, unknown>).theorem));
          }
        }
      }
      for (const theorem of CONCRETE_PROOF_OBLIGATIONS) {
        if (!passed.has(theorem)) {
          errors.push(
            `root: lean_proof_checked obligations missing passed proofs for ${JSON.stringify(theorem)}`,
          );
        }
      }
    }
  }
  return errors;
}

const AUTHORIZATION_TO_DECISION: Record<string, string> = {
  authorized: "allow",
  rejected: "deny",
  unknown: "deny",
  policy_missing: "deny",
};

function defaultFieldLayer(section: string, field: string): string {
  const key = `${section}.${field}`;
  const mapping: Record<string, string> = {
    "pre.require_capability": "lean",
    "pre.require_effect": "lean",
    "pre.require_tenant_match": "lean",
    "pre.require_role": "runtime",
    "pre.require_policy_ref": "runtime",
    "pre.require_evidence_ref": "runtime",
    "post.require_decision": "lean",
    "post.require_event_safe": "lean",
    "invariant.require_trace_safe": "lean",
  };
  return mapping[key] ?? "runtime";
}

function fieldLayer(contract: Record<string, unknown>, section: string, field: string): string {
  const semantics = contract.semantics_layer;
  if (semantics && typeof semantics === "object" && !Array.isArray(semantics)) {
    const layer = (semantics as Record<string, unknown>)[field];
    if (typeof layer === "string") {
      return layer;
    }
  }
  return defaultFieldLayer(section, field);
}

function principalHasCapability(principal: Record<string, unknown>, capabilityId: string): boolean {
  const caps = principal.capabilities;
  if (!Array.isArray(caps)) {
    return false;
  }
  return caps.some((cap) => String(cap) === capabilityId);
}

function actionHasEffect(action: Record<string, unknown>, effectKind: string): boolean {
  const effects = action.effects;
  if (!Array.isArray(effects)) {
    return false;
  }
  return effects.some(
    (effect) =>
      effect &&
      typeof effect === "object" &&
      !Array.isArray(effect) &&
      String((effect as Record<string, unknown>).effect_kind ?? "") === effectKind,
  );
}

function tenantMatches(principal: Record<string, unknown>, action: Record<string, unknown>): boolean {
  const tenant = String(principal.tenant ?? "");
  for (const key of ["reads", "writes"]) {
    const resources = action[key];
    if (!Array.isArray(resources)) {
      continue;
    }
    for (const resource of resources) {
      if (
        resource &&
        typeof resource === "object" &&
        !Array.isArray(resource) &&
        String((resource as Record<string, unknown>).tenant ?? "") !== tenant
      ) {
        return false;
      }
    }
  }
  return true;
}

export function validateEventAgainstContract(
  event: Record<string, unknown>,
  contract: Record<string, unknown>,
  path: string,
): string[] {
  const errors: string[] = [];
  const principal = event.principal;
  const action = event.action;
  if (!principal || typeof principal !== "object" || Array.isArray(principal)) {
    return [`ContractEventInvalid: event missing principal or action at ${path}`];
  }
  if (!action || typeof action !== "object" || Array.isArray(action)) {
    return [`ContractEventInvalid: event missing principal or action at ${path}`];
  }
  const principalObj = principal as Record<string, unknown>;
  const actionObj = action as Record<string, unknown>;
  const contractId = String(contract.contract_id ?? "");

  const pre = contract.pre;
  if (pre && typeof pre === "object" && !Array.isArray(pre)) {
    const preObj = pre as Record<string, unknown>;
    if (
      preObj.require_tenant_match === true &&
      fieldLayer(contract, "pre", "require_tenant_match") !== "out_of_scope" &&
      !tenantMatches(principalObj, actionObj)
    ) {
      errors.push(
        `ContractTenantMismatch: contract ${JSON.stringify(contractId)} requires tenant match at ${path}`,
      );
    }
    const requiredCap = preObj.require_capability;
    if (
      typeof requiredCap === "string" &&
      requiredCap &&
      fieldLayer(contract, "pre", "require_capability") !== "out_of_scope" &&
      !principalHasCapability(principalObj, requiredCap)
    ) {
      errors.push(
        `ContractCapabilityRequired: contract ${JSON.stringify(contractId)} requires capability ${JSON.stringify(requiredCap)} at ${path}.principal`,
      );
    }
    const requiredEffect = preObj.require_effect;
    if (
      typeof requiredEffect === "string" &&
      requiredEffect &&
      fieldLayer(contract, "pre", "require_effect") !== "out_of_scope" &&
      !actionHasEffect(actionObj, requiredEffect)
    ) {
      errors.push(
        `ContractEffectRequired: contract ${JSON.stringify(contractId)} requires effect ${JSON.stringify(requiredEffect)} at ${path}.action.effects`,
      );
    }
    const requiredRole = preObj.require_role;
    if (
      typeof requiredRole === "string" &&
      requiredRole &&
      fieldLayer(contract, "pre", "require_role") !== "out_of_scope"
    ) {
      const roles = principalObj.roles;
      const hasRole =
        Array.isArray(roles) && roles.some((role) => String(role) === requiredRole);
      if (!hasRole) {
        errors.push(
          `ContractRoleRequired: contract ${JSON.stringify(contractId)} requires role ${JSON.stringify(requiredRole)} at ${path}.principal.roles`,
        );
      }
    }
    const requiredPolicy = preObj.require_policy_ref;
    if (
      typeof requiredPolicy === "string" &&
      requiredPolicy &&
      fieldLayer(contract, "pre", "require_policy_ref") !== "out_of_scope"
    ) {
      const refs = event.contract_refs;
      const hasRef =
        Array.isArray(refs) && refs.some((ref) => String(ref) === requiredPolicy);
      if (!hasRef) {
        errors.push(
          `ContractPolicyRefRequired: contract ${JSON.stringify(contractId)} requires policy ref ${JSON.stringify(requiredPolicy)} at ${path}.contract_refs`,
        );
      }
    }
    const requiredEvidence = preObj.require_evidence_ref;
    if (
      typeof requiredEvidence === "string" &&
      requiredEvidence &&
      fieldLayer(contract, "pre", "require_evidence_ref") !== "out_of_scope"
    ) {
      const evidence = event.evidence_refs;
      const hasRef =
        Array.isArray(evidence) && evidence.some((ref) => String(ref) === requiredEvidence);
      if (!hasRef) {
        errors.push(
          `ContractEvidenceRefRequired: contract ${JSON.stringify(contractId)} requires evidence ref ${JSON.stringify(requiredEvidence)} at ${path}.evidence_refs`,
        );
      }
    }
  }

  const post = contract.post;
  if (post && typeof post === "object" && !Array.isArray(post)) {
    const postObj = post as Record<string, unknown>;
    const requiredDecision = postObj.require_decision;
    if (
      typeof requiredDecision === "string" &&
      requiredDecision &&
      fieldLayer(contract, "post", "require_decision") !== "out_of_scope"
    ) {
      const decision = String(event.decision ?? "");
      if (decision !== requiredDecision) {
        errors.push(
          `ContractDecisionMismatch: contract ${JSON.stringify(contractId)} requires decision ${JSON.stringify(requiredDecision)}, got ${JSON.stringify(decision)} at ${path}.decision`,
        );
      }
    }
    if (
      postObj.require_event_safe === true &&
      fieldLayer(contract, "post", "require_event_safe") !== "out_of_scope"
    ) {
      const decision = String(event.decision ?? "");
      if (decision === "allow") {
        const capability = actionObj.capability;
        const capId =
          capability &&
          typeof capability === "object" &&
          !Array.isArray(capability)
            ? String((capability as Record<string, unknown>).capability_id ?? "")
            : "";
        if (!capId || !principalHasCapability(principalObj, capId)) {
          errors.push(
            `ContractEventUnsafe: allowed event violates contract ${JSON.stringify(contractId)} event safety at ${path}`,
          );
        } else if (!tenantMatches(principalObj, actionObj)) {
          errors.push(
            `ContractEventUnsafe: allowed event violates contract ${JSON.stringify(contractId)} tenant safety at ${path}`,
          );
        }
      }
    }
  }

  return errors;
}

export function validateTraceContracts(
  trace: Record<string, unknown>,
  contracts: Record<string, Record<string, unknown>>,
): string[] {
  const errors: string[] = [];
  const events = trace.events;
  if (!Array.isArray(events)) {
    return ["TraceInvalid: events must be an array"];
  }
  for (let index = 0; index < events.length; index += 1) {
    const base = `events[${index}]`;
    const event = events[index];
    if (!event || typeof event !== "object" || Array.isArray(event)) {
      continue;
    }
    const refs = (event as Record<string, unknown>).contract_refs;
    if (!Array.isArray(refs) || refs.length === 0) {
      continue;
    }
    for (let refIndex = 0; refIndex < refs.length; refIndex += 1) {
      const contractId = String(refs[refIndex] ?? "");
      const contract = contracts[contractId];
      if (!contract) {
        errors.push(
          `ContractRefMissing: unknown contract reference ${JSON.stringify(contractId)} at ${base}.contract_refs[${refIndex}]`,
        );
        continue;
      }
      errors.push(
        ...validateEventAgainstContract(event as Record<string, unknown>, contract, base),
      );
    }
  }
  return errors;
}

export function validateDeniedEventsPreserved(
  toolUseTrace: Record<string, unknown>,
  pfcoreTrace: Record<string, unknown>,
): string[] {
  const toolCalls = toolUseTrace.tool_calls;
  if (!Array.isArray(toolCalls)) {
    return [];
  }
  const events = pfcoreTrace.events;
  if (!Array.isArray(events)) {
    return [
      'DroppedDeniedEvent: denied event "<missing-events>" missing from compiled trace (at events)',
    ];
  }
  const compiledIds = new Set(
    events
      .filter((event) => event && typeof event === "object" && !Array.isArray(event))
      .map((event) => String((event as Record<string, unknown>).event_id ?? "")),
  );
  const errors: string[] = [];
  for (const toolCall of toolCalls) {
    if (!toolCall || typeof toolCall !== "object" || Array.isArray(toolCall)) {
      continue;
    }
    const auth = String((toolCall as Record<string, unknown>).authorization_status ?? "");
    const decision = AUTHORIZATION_TO_DECISION[auth] ?? "deny";
    if (decision !== "deny") {
      continue;
    }
    const eventId = String((toolCall as Record<string, unknown>).event_id ?? "");
    if (eventId && !compiledIds.has(eventId)) {
      errors.push(
        `DroppedDeniedEvent: denied event ${JSON.stringify(eventId)} missing from compiled trace (at events)`,
      );
    }
  }
  return errors;
}
