import { canonicalHash, canonicalJsonBytes } from "./hash.js";
import {
  CAPABILITY_CATALOG,
  EFFECT_KINDS,
} from "./pfCoreCatalog.js";

export { CAPABILITY_CATALOG, EFFECT_KINDS, ROLE_CAPABILITY_MAP } from "./pfCoreCatalog.js";

export const GENESIS_HASH =
  "sha256:0000000000000000000000000000000000000000000000000000000000000000";

export type CapabilityEntry = {
  capability_id: string;
  effect_kind: string;
  resource_pattern: string;
};

function runtimeError(code: string, message: string, path: string): string {
  return `${code}: ${message} (at ${path})`;
}

function globMatch(pattern: string, text: string): boolean {
  const patternChars = [...pattern];
  const textChars = [...text];
  function rec(pi: number, ti: number): boolean {
    if (pi === patternChars.length) {
      return ti === textChars.length;
    }
    if (patternChars[pi] === "*") {
      if (pi + 1 === patternChars.length) {
        return true;
      }
      for (let j = ti; j <= textChars.length; j += 1) {
        if (rec(pi + 1, j)) {
          return true;
        }
      }
      return false;
    }
    if (ti >= textChars.length || patternChars[pi] !== textChars[ti]) {
      return false;
    }
    return rec(pi + 1, ti + 1);
  }
  return rec(0, 0);
}

export function resourceMatchesPattern(uri: string, pattern: string): boolean {
  if (pattern === "*") {
    return true;
  }
  return globMatch(pattern, uri);
}

function validateActionEffectsKnown(
  action: Record<string, unknown>,
  path: string,
): string | null {
  const effects = action.effects;
  if (!Array.isArray(effects)) {
    return runtimeError("UnknownEffect", "unknown effect: <missing>", `${path}.effects`);
  }
  if (effects.length === 0) {
    return runtimeError("UnknownEffect", "unknown effect: <missing>", path);
  }
  for (let index = 0; index < effects.length; index += 1) {
    const effect = effects[index];
    if (!effect || typeof effect !== "object" || Array.isArray(effect)) {
      return runtimeError(
        "UnknownEffect",
        "unknown effect: <invalid>",
        `${path}.effects[${index}]`,
      );
    }
    const kind = String((effect as Record<string, unknown>).effect_kind ?? "");
    if (!kind || !EFFECT_KINDS.has(kind)) {
      return runtimeError(
        "UnknownEffect",
        `unknown effect: ${kind || "<missing>"}`,
        `${path}.effects[${index}].effect_kind`,
      );
    }
  }
  return null;
}

function validateActionCapabilitiesKnown(
  action: Record<string, unknown>,
  path: string,
): string | null {
  const capability = action.capability;
  if (!capability || typeof capability !== "object" || Array.isArray(capability)) {
    return runtimeError(
      "UnknownCapability",
      "unknown capability: <missing>",
      `${path}.capability`,
    );
  }
  const capObj = capability as Record<string, unknown>;
  const capId = String(capObj.capability_id ?? "");
  if (!capId || !CAPABILITY_CATALOG[capId]) {
    return runtimeError(
      "UnknownCapability",
      `unknown capability: ${capId || "<missing>"}`,
      `${path}.capability`,
    );
  }
  const effectKind = String(capObj.effect_kind ?? "");
  if (!effectKind || !EFFECT_KINDS.has(effectKind)) {
    return runtimeError(
      "UnknownEffect",
      `unknown effect: ${effectKind || "<missing>"}`,
      `${path}.capability.effect_kind`,
    );
  }
  return null;
}

function validateActionCapabilityEffects(
  action: Record<string, unknown>,
  path: string,
): string | null {
  const capability = action.capability;
  if (!capability || typeof capability !== "object" || Array.isArray(capability)) {
    return runtimeError(
      "UnknownCapability",
      "unknown capability: <missing>",
      `${path}.capability`,
    );
  }
  const capId = String((capability as Record<string, unknown>).capability_id ?? "");
  const catalog = CAPABILITY_CATALOG[capId];
  if (!catalog) {
    return runtimeError(
      "UnknownCapability",
      `unknown capability: ${capId || "<missing>"}`,
      `${path}.capability`,
    );
  }
  const effectsError = validateActionEffectsKnown(action, path);
  if (effectsError) {
    return effectsError;
  }
  if (!actionHasEffect(action, catalog.effect_kind)) {
    return runtimeError(
      "CapabilityEffectMismatch",
      `capability ${JSON.stringify(catalog.capability_id)} effect_kind ${JSON.stringify(catalog.effect_kind)} not listed in action effects`,
      `${path}.effects`,
    );
  }
  return null;
}

function validateResourceScope(action: Record<string, unknown>, path: string): string | null {
  const capability = action.capability;
  if (!capability || typeof capability !== "object" || Array.isArray(capability)) {
    return null;
  }
  const pattern = String((capability as Record<string, unknown>).resource_pattern ?? "");
  if (!pattern) {
    return null;
  }
  for (const key of ["reads", "writes"]) {
    const resources = action[key];
    if (!Array.isArray(resources)) {
      continue;
    }
    for (let index = 0; index < resources.length; index += 1) {
      const resource = resources[index];
      if (!resource || typeof resource !== "object" || Array.isArray(resource)) {
        continue;
      }
      const uri = String((resource as Record<string, unknown>).uri ?? "");
      if (uri && !resourceMatchesPattern(uri, pattern)) {
        return runtimeError(
          "ResourceScopeViolation",
          `resource ${JSON.stringify(uri)} outside declared pattern ${JSON.stringify(pattern)}`,
          `${path}.${key}[${index}].uri`,
        );
      }
    }
  }
  return null;
}

export function validateDirectTraceActionSemantics(trace: Record<string, unknown>): string[] {
  const errors: string[] = [];
  const events = trace.events;
  if (!Array.isArray(events)) {
    return errors;
  }
  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    if (!event || typeof event !== "object" || Array.isArray(event)) {
      continue;
    }
    const action = (event as Record<string, unknown>).action;
    if (!action || typeof action !== "object" || Array.isArray(action)) {
      continue;
    }
    const actionObj = action as Record<string, unknown>;
    const base = `events[${index}].action`;
    const effectError = validateActionEffectsKnown(actionObj, base);
    if (effectError) {
      errors.push(effectError);
    }
    const capabilityError = validateActionCapabilitiesKnown(actionObj, base);
    if (capabilityError) {
      errors.push(capabilityError);
    }
    const mismatchError = validateActionCapabilityEffects(actionObj, base);
    if (mismatchError) {
      errors.push(mismatchError);
    }
  }
  return errors;
}

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

const DEFAULT_TRACE_SAFE_CONTRACT_ID = "trace-safe";
const RUNTIME_RESOURCE_PATTERN_SCOPE = "resource_pattern_scope";
const LEAN_RESOURCE_WITHIN_CAPABILITY_PATTERN = "resource_within_capability_pattern";

export type ContractSemanticsChecked = {
  lean: string[];
  runtime: string[];
};

function contractSemanticsStringList(value: unknown): string[] | null {
  if (value === undefined || value === null) {
    return [];
  }
  if (!Array.isArray(value)) {
    return null;
  }
  const out: string[] = [];
  for (const item of value) {
    if (typeof item !== "string") {
      return null;
    }
    out.push(item);
  }
  return out;
}

/** Parse `contract_semantics_checked` when present and well-formed. */
export function parseContractSemanticsChecked(
  certificate: Record<string, unknown>,
): ContractSemanticsChecked | null {
  const semantics = certificate.contract_semantics_checked;
  if (!semantics || typeof semantics !== "object" || Array.isArray(semantics)) {
    return null;
  }
  const obj = semantics as Record<string, unknown>;
  const lean = contractSemanticsStringList(obj.lean);
  const runtime = contractSemanticsStringList(obj.runtime);
  if (lean === null || runtime === null) {
    return null;
  }
  return { lean, runtime };
}

/** Validate certificate contract-semantics metadata (does not imply LeanKernelChecked). */
export function validateContractSemanticsChecked(
  certificate: Record<string, unknown>,
): string[] {
  const errors: string[] = [];
  const claimClass = String(certificate.claim_class ?? "");
  const leanProofChecked = certificate.lean_proof_checked === true;
  const semantics = certificate.contract_semantics_checked;

  if (semantics !== undefined && semantics !== null) {
    if (typeof semantics !== "object" || Array.isArray(semantics)) {
      errors.push("root: contract_semantics_checked must be an object");
      return errors;
    }
    const obj = semantics as Record<string, unknown>;
    for (const key of ["lean", "runtime"] as const) {
      if (obj[key] === undefined) {
        continue;
      }
      const list = contractSemanticsStringList(obj[key]);
      if (list === null) {
        errors.push(`root: contract_semantics_checked.${key} must be a string array`);
      }
    }
  }

  if (claimClass === "LeanKernelChecked") {
    const defaultRef = String(certificate.default_contract_ref ?? "");
    const parsed = parseContractSemanticsChecked(certificate);
    const hasSemantics =
      parsed !== null && (parsed.lean.length > 0 || parsed.runtime.length > 0);
    if (defaultRef !== DEFAULT_TRACE_SAFE_CONTRACT_ID && !hasSemantics) {
      errors.push(
        `root: claim_class LeanKernelChecked requires contract_refs or default_contract_ref ${JSON.stringify(DEFAULT_TRACE_SAFE_CONTRACT_ID)}`,
      );
    }
  }

  if (leanProofChecked) {
    const parsed = parseContractSemanticsChecked(certificate);
    if (parsed === null) {
      if (semantics !== undefined && semantics !== null) {
        errors.push("root: contract_semantics_checked has invalid shape");
      } else {
        errors.push("root: lean_proof_checked requires contract_semantics_checked");
      }
    } else {
      if (!parsed.runtime.includes(RUNTIME_RESOURCE_PATTERN_SCOPE)) {
        errors.push(
          `root: lean_proof_checked contract_semantics_checked.runtime missing ${JSON.stringify(RUNTIME_RESOURCE_PATTERN_SCOPE)}`,
        );
      }
      if (!parsed.lean.includes(LEAN_RESOURCE_WITHIN_CAPABILITY_PATTERN)) {
        errors.push(
          `root: lean_proof_checked contract_semantics_checked.lean missing ${JSON.stringify(LEAN_RESOURCE_WITHIN_CAPABILITY_PATTERN)}`,
        );
      }
    }
  }

  return errors;
}

const DEFAULT_CERTIFICATE_MODE = "TraceSafeCertificate";

const CERTIFICATE_MODES = new Set([
  "TraceSafeCertificate",
  "TraceSafeRCertificate",
  "FramePreservedCertificate",
  "EffectFrameCertificate",
  "HandoffSafeCertificate",
  "CompositionalExtensionCertificate",
  "ContractCheckedCertificate",
]);

const MODE_OBLIGATION_THEOREMS: Record<string, readonly string[]> = {
  TraceSafeCertificate: [
    "concrete_trace_safe",
    "concrete_trace_safe_prop",
    "concrete_allowed_events_allowed",
  ],
  TraceSafeRCertificate: [
    "concrete_trace_safe",
    "concrete_trace_safe_prop",
    "concrete_allowed_events_allowed",
    "concrete_trace_safe_r",
    "concrete_trace_safe_r_prop",
    "concrete_trace_safe_r_implies_trace_safe",
  ],
  FramePreservedCertificate: [
    "concrete_trace_safe",
    "concrete_trace_safe_prop",
    "concrete_allowed_events_allowed",
    "frame_valid_initial",
    "frame_preserved_steps",
  ],
  EffectFrameCertificate: [
    "concrete_trace_safe",
    "concrete_trace_safe_prop",
    "concrete_allowed_events_allowed",
    "concrete_action_effects_in_frame",
  ],
  HandoffSafeCertificate: [
    "concrete_trace_safe",
    "concrete_trace_safe_prop",
    "concrete_allowed_events_allowed",
    "concrete_handoff_safe",
  ],
  CompositionalExtensionCertificate: [
    "concrete_trace_safe",
    "concrete_trace_safe_prop",
    "concrete_allowed_events_allowed",
    "concrete_compositional_extension",
  ],
  ContractCheckedCertificate: [
    "concrete_trace_safe",
    "concrete_trace_safe_prop",
    "concrete_allowed_events_allowed",
    "concrete_contract_checked",
  ],
};

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

  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    if (!event || typeof event !== "object" || Array.isArray(event)) {
      continue;
    }
    const action = (event as Record<string, unknown>).action;
    if (!action || typeof action !== "object" || Array.isArray(action)) {
      continue;
    }
    const scopeError = validateResourceScope(action as Record<string, unknown>, `events[${index}].action`);
    if (scopeError) {
      errors.push(scopeError);
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
    const kernelHash = certificate.pfcore_kernel_hash;
    if (typeof kernelHash !== "string" || !kernelHash.startsWith("sha256:")) {
      errors.push("root: claim_class LeanKernelChecked requires pfcore_kernel_hash");
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
      const certMode = String(certificate.certificate_mode ?? DEFAULT_CERTIFICATE_MODE);
      if (!CERTIFICATE_MODES.has(certMode)) {
        errors.push(`root: invalid certificate_mode ${JSON.stringify(certMode)}`);
      } else {
        const modeRequired = new Set(MODE_OBLIGATION_THEOREMS[certMode] ?? []);
        if (Array.isArray(certificate.obligations)) {
          for (const item of certificate.obligations) {
            if (
              item &&
              typeof item === "object" &&
              !Array.isArray(item) &&
              typeof (item as Record<string, unknown>).theorem === "string"
            ) {
              const theorem = String((item as Record<string, unknown>).theorem);
              if (theorem.startsWith("concrete_action_resource_scope_")) {
                modeRequired.add(theorem);
              }
            }
          }
        }
        const missingMode = [...modeRequired].filter((theorem) => !passed.has(theorem));
        if (missingMode.length > 0) {
          errors.push(
            `root: certificate_mode obligations missing passed proofs for ${JSON.stringify(missingMode)}`,
          );
        }
      }
    } else {
      const certMode = String(certificate.certificate_mode ?? DEFAULT_CERTIFICATE_MODE);
      if (!CERTIFICATE_MODES.has(certMode)) {
        errors.push(`root: invalid certificate_mode ${JSON.stringify(certMode)}`);
      }
    }
  }
  errors.push(...validateContractSemanticsChecked(certificate));
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

function actionWithinTenantD(principal: Record<string, unknown>, action: Record<string, unknown>): boolean {
  const tenant = String(principal.tenant ?? "");
  for (const key of ["reads", "writes"]) {
    const resources = action[key];
    if (!Array.isArray(resources)) {
      return false;
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

function actionAdmissibleD(principal: Record<string, unknown>, action: Record<string, unknown>): boolean {
  const capability = action.capability;
  if (!capability || typeof capability !== "object" || Array.isArray(capability)) {
    return false;
  }
  const capId = String((capability as Record<string, unknown>).capability_id ?? "");
  const path = "action";
  if (
    validateActionCapabilitiesKnown(action, path) ||
    validateActionEffectsKnown(action, path) ||
    validateActionCapabilityEffects(action, path) ||
    validateResourceScope(action, path)
  ) {
    return false;
  }
  return principalHasCapability(principal, capId) && actionWithinTenantD(principal, action);
}

/** Mirror Lean `actionAdmissibleWithResourcePatternD` (kernel + catalog resource scope). */
export function actionAdmissibleWithResourcePatternD(
  principal: Record<string, unknown>,
  action: Record<string, unknown>,
): boolean {
  return actionAdmissibleD(principal, action);
}

/** Mirror Lean `eventSafeD` on allow events (deny is vacuously safe). */
export function eventSafeD(event: Record<string, unknown>): boolean {
  const decision = String(event.decision ?? "");
  if (decision === "deny") {
    return true;
  }
  if (decision !== "allow") {
    return false;
  }
  const principal = event.principal;
  const action = event.action;
  if (!principal || typeof principal !== "object" || Array.isArray(principal)) {
    return false;
  }
  if (!action || typeof action !== "object" || Array.isArray(action)) {
    return false;
  }
  return actionAdmissibleD(principal as Record<string, unknown>, action as Record<string, unknown>);
}

/** Mirror Lean `eventSafeRD` (allow branch uses resource-pattern admissibility). */
export function eventSafeRD(event: Record<string, unknown>): boolean {
  const decision = String(event.decision ?? "");
  if (decision === "deny") {
    return true;
  }
  if (decision !== "allow") {
    return false;
  }
  const principal = event.principal;
  const action = event.action;
  if (!principal || typeof principal !== "object" || Array.isArray(principal)) {
    return false;
  }
  if (!action || typeof action !== "object" || Array.isArray(action)) {
    return false;
  }
  return actionAdmissibleWithResourcePatternD(
    principal as Record<string, unknown>,
    action as Record<string, unknown>,
  );
}

/** Mirror Lean `traceSafeD` decider. */
export function traceSafeD(events: Record<string, unknown>[]): boolean {
  return events.every((event) => eventSafeD(event));
}

/** Mirror Lean `traceSafeRD` (resource-pattern trace safety decider). */
export function traceSafeRD(events: Record<string, unknown>[]): boolean {
  return events.every((event) => eventSafeRD(event));
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


function lowEventForTenant(tenant: string, event: Record<string, unknown>): boolean {
  if (String(event.decision ?? "") !== "allow") {
    return false;
  }
  const principal = event.principal;
  if (!principal || typeof principal !== "object" || Array.isArray(principal)) {
    return false;
  }
  return String((principal as Record<string, unknown>).tenant ?? "") === tenant;
}

function traceProjectionForTenant(
  trace: Record<string, unknown>,
  tenant: string,
): Record<string, unknown>[] {
  const projection: Record<string, unknown>[] = [];
  const events = trace.events;
  if (!Array.isArray(events)) {
    return projection;
  }
  for (const event of events) {
    if (event && typeof event === "object" && !Array.isArray(event)) {
      const eventObj = event as Record<string, unknown>;
      if (lowEventForTenant(tenant, eventObj)) {
        projection.push(eventObj);
      }
    }
  }
  return projection;
}

export function validateObservationalNonInterference(
  trace: Record<string, unknown>,
  tenantLow: string,
  tenantHigh: string,
): string[] {
  if (tenantLow === tenantHigh) {
    return [];
  }
  const errors: string[] = [];
  const events = trace.events;
  if (!Array.isArray(events)) {
    return ["TraceInvalid: events must be an array"];
  }
  const projection = traceProjectionForTenant(trace, tenantLow);
  for (let index = 0; index < projection.length; index += 1) {
    if (!lowEventForTenant(tenantLow, projection[index]!)) {
      errors.push(
        `NonInterference: projected event at projection[${index}] is not LowEvent for tenant ${JSON.stringify(tenantLow)}`,
      );
    }
  }
  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    if (!event || typeof event !== "object" || Array.isArray(event)) {
      continue;
    }
    const eventObj = event as Record<string, unknown>;
    const principal = eventObj.principal;
    if (!principal || typeof principal !== "object" || Array.isArray(principal)) {
      continue;
    }
    if (String((principal as Record<string, unknown>).tenant ?? "") !== tenantHigh) {
      continue;
    }
    if (lowEventForTenant(tenantLow, eventObj)) {
      errors.push(
        `NonInterference: high-tenant event at events[${index}] is low-visible to tenant ${JSON.stringify(tenantLow)}`,
      );
    }
  }
  return errors;
}

export function validateObservationalNonInterferenceAllPairs(trace: Record<string, unknown>): string[] {
  const tenants: string[] = [];
  const events = trace.events;
  if (Array.isArray(events)) {
    for (const event of events) {
      if (!event || typeof event !== "object" || Array.isArray(event)) {
        continue;
      }
      const principal = (event as Record<string, unknown>).principal;
      if (principal && typeof principal === "object" && !Array.isArray(principal)) {
        const tenant = String((principal as Record<string, unknown>).tenant ?? "");
        if (tenant && !tenants.includes(tenant)) {
          tenants.push(tenant);
        }
      }
    }
  }
  const errors: string[] = [];
  for (const tenantLow of tenants) {
    for (const tenantHigh of tenants) {
      if (tenantLow === tenantHigh) {
        continue;
      }
      errors.push(...validateObservationalNonInterference(trace, tenantLow, tenantHigh));
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

function eventCrossTenantSafe(
  principal: Record<string, unknown>,
  action: Record<string, unknown>,
  decision: string,
): boolean {
  if (decision === "deny") {
    return true;
  }
  return tenantMatches(principal, action);
}

export function validateCrossTenantSafety(trace: Record<string, unknown>): string[] {
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
    const eventObj = event as Record<string, unknown>;
    const principal = eventObj.principal;
    const action = eventObj.action;
    if (
      !principal ||
      typeof principal !== "object" ||
      Array.isArray(principal) ||
      !action ||
      typeof action !== "object" ||
      Array.isArray(action)
    ) {
      errors.push(`CrossTenantSafe: ${base} missing principal or action`);
      continue;
    }
    const decision = String(eventObj.decision ?? "");
    if (
      !eventCrossTenantSafe(
        principal as Record<string, unknown>,
        action as Record<string, unknown>,
        decision,
      )
    ) {
      const tenant = String((principal as Record<string, unknown>).tenant ?? "");
      errors.push(
        `CrossTenantSafe: cross-tenant allow at ${base} (principal tenant ${JSON.stringify(tenant)})`,
      );
    }
  }
  return errors;
}

export function validateTenantIsolation(trace: Record<string, unknown>): string[] {
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
    const eventObj = event as Record<string, unknown>;
    const principal = eventObj.principal;
    const action = eventObj.action;
    if (
      !principal ||
      typeof principal !== "object" ||
      Array.isArray(principal) ||
      !action ||
      typeof action !== "object" ||
      Array.isArray(action)
    ) {
      errors.push(`TenantIsolation: ${base} missing principal or action`);
      continue;
    }
    const tenant = String((principal as Record<string, unknown>).tenant ?? "");
    if (!tenant) {
      errors.push(`TenantIsolation: ${base}.principal.tenant is empty`);
      continue;
    }
    if (!tenantMatches(principal as Record<string, unknown>, action as Record<string, unknown>)) {
      errors.push(
        `TenantIsolation: cross-tenant resource access at ${base} (principal tenant ${JSON.stringify(tenant)})`,
      );
    }
  }
  return errors;
}
