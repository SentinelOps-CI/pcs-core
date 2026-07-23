import type { ErrorObject, ValidateFunction } from "ajv";
import { createRequire } from "node:module";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import type { ArtifactType } from "./validate.js";

const require = createRequire(import.meta.url);
const Ajv2020 = require("ajv/dist/2020") as new (options?: {
  strict?: boolean;
  allErrors?: boolean;
  validateSchema?: boolean;
}) => {
  addSchema(schema: object, key?: string): void;
  getSchema(key: string): ValidateFunction | undefined;
};
const addFormats = require("ajv-formats") as (
  ajv: InstanceType<typeof Ajv2020>,
) => InstanceType<typeof Ajv2020>;

const SCHEMAS_ROOT = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../schemas",
);

const ARTIFACT_SCHEMAS: Record<ArtifactType, string> = {
  "AssumptionSet.v0": "AssumptionSet.v0.schema.json",
  "SourceSpan.v0": "SourceSpan.v0.schema.json",
  "ClaimArtifact.v0": "ClaimArtifact.v0.schema.json",
  "RuntimeReceipt.v0": "RuntimeReceipt.v0.schema.json",
  "TraceCertificate.v0": "TraceCertificate.v0.schema.json",
  "EvidenceBundle.v0": "EvidenceBundle.v0.schema.json",
  "ScienceClaimBundle.v0": "ScienceClaimBundle.v0.schema.json",
  "VerificationResult.v0": "VerificationResult.v0.schema.json",
  "SignedScienceClaimBundle.v0": "SignedScienceClaimBundle.v0.schema.json",
  "ReleaseManifest.v0": "ReleaseManifest.v0.schema.json",
  "HandoffManifest.v0": "HandoffManifest.v0.schema.json",
  "ReleaseChainValidationResult.v0": "ReleaseChainValidationResult.v0.schema.json",
  "ArtifactRegistry.v0": "ArtifactRegistry.v0.schema.json",
  "SemanticCheckExecution.v0": "SemanticCheckExecution.v0.schema.json",
  "ComponentReleaseFragment.v0": "ComponentReleaseFragment.v0.schema.json",
  "MigrationReport.v0": "MigrationReport.v0.schema.json",
  "WorkflowProfile.v0": "WorkflowProfile.v0.schema.json",
  "ToolUseTrace.v0": "ToolUseTrace.v0.schema.json",
  "ToolUseCertificate.v0": "ToolUseCertificate.v0.schema.json",
  "DatasetReceipt.v0": "DatasetReceipt.v0.schema.json",
  "EnvironmentReceipt.v0": "EnvironmentReceipt.v0.schema.json",
  "ComputationRunReceipt.v0": "ComputationRunReceipt.v0.schema.json",
  "ResultArtifact.v0": "ResultArtifact.v0.schema.json",
  "ComputationWitness.v0": "ComputationWitness.v0.schema.json",
  "ProofObligation.v0": "ProofObligation.v0.schema.json",
  "LeanCheckResult.v0": "LeanCheckResult.v0.schema.json",
  "BenchmarkRegistry.v0": "BenchmarkRegistry.v0.schema.json",
  "BenchmarkSuiteManifest.v0": "BenchmarkSuiteManifest.v0.schema.json",
  "BenchmarkTask.v0": "BenchmarkTask.v0.schema.json",
  "BenchmarkCase.v0": "BenchmarkCase.v0.schema.json",
  "BenchmarkRun.v0": "BenchmarkRun.v0.schema.json",
  "BenchmarkReport.v0": "BenchmarkReport.v0.schema.json",
  "MetricSummary.v0": "MetricSummary.v0.schema.json",
  "PcsBenchIngest.v0": "PcsBenchIngest.v0.schema.json",
  "BenchmarkArtifactRef.v0": "BenchmarkArtifactRef.v0.schema.json",
  "ConformanceRun.v0": "ConformanceRun.v0.schema.json",
  "FailureCaseManifest.v0": "FailureCaseManifest.v0.schema.json",
  "FailureLocalizationResult.v0": "FailureLocalizationResult.v0.schema.json",
  "CoverageReport.v0": "CoverageReport.v0.schema.json",
  "ExplainQualityReport.v0": "ExplainQualityReport.v0.schema.json",
  "ProfileCoverageReport.v0": "ProfileCoverageReport.v0.schema.json",
  "BenchmarkMetricRegistry.v0": "BenchmarkMetricRegistry.v0.schema.json",
  "ConformanceReport.v0": "ConformanceReport.v0.schema.json",
  "PFCorePrincipal.v0": "PFCorePrincipal.v0.schema.json",
  "PFCoreCapability.v0": "PFCoreCapability.v0.schema.json",
  "PFCoreResource.v0": "PFCoreResource.v0.schema.json",
  "PFCoreAction.v0": "PFCoreAction.v0.schema.json",
  "PFCoreEffect.v0": "PFCoreEffect.v0.schema.json",
  "PFCoreDecision.v0": "PFCoreDecision.v0.schema.json",
  "PFCoreEvent.v0": "PFCoreEvent.v0.schema.json",
  "PFCoreTrace.v0": "PFCoreTrace.v0.schema.json",
  "PFCoreContract.v0": "PFCoreContract.v0.schema.json",
  "PFCoreHandoff.v0": "PFCoreHandoff.v0.schema.json",
  "PFCoreRuntimeObservation.v0": "PFCoreRuntimeObservation.v0.schema.json",
  "PFCoreCertificate.v0": "PFCoreCertificate.v0.schema.json",
  "PFCoreSemanticProjection.v0": "PFCoreSemanticProjection.v0.schema.json",
  "PCSBridgeCertificate.v0": "PCSBridgeCertificate.v0.schema.json",
  "PFCoreKernelManifest.v0": "PFCoreKernelManifest.v0.schema.json",
  "PFCoreReleaseBundleManifest.v0": "PFCoreReleaseBundleManifest.v0.schema.json",
  "ArtifactIntegrity.v1": "ArtifactIntegrity.v1.schema.json",
  "FormatAssertionProbe.v0": "FormatAssertionProbe.v0.schema.json",
  "ExternalAttestation.v0": "ExternalAttestation.v0.schema.json",
};


type Ajv = InstanceType<typeof Ajv2020>;

let ajvInstance: Ajv | null = null;

function getAjv(): Ajv {
  if (ajvInstance) return ajvInstance;
  const ajv = new Ajv2020({
    strict: true,
    allErrors: true,
    validateSchema: false,
  });
  addFormats(ajv);
  for (const file of readdirSync(SCHEMAS_ROOT).filter((f) => f.endsWith(".json"))) {
    const schema = JSON.parse(readFileSync(join(SCHEMAS_ROOT, file), "utf8")) as object;
    const id = (schema as { $id?: string }).$id ?? file;
    ajv.addSchema(schema, id);
  }
  ajvInstance = ajv;
  return ajv;
}

export function validateSchema(data: unknown, artifactType: ArtifactType): string[] {
  const ajv = getAjv();
  const schemaFile = ARTIFACT_SCHEMAS[artifactType];
  const schema = JSON.parse(
    readFileSync(join(SCHEMAS_ROOT, schemaFile), "utf8"),
  ) as { $id?: string };
  const validate = ajv.getSchema(schema.$id ?? schemaFile);
  if (!validate) {
    return [`schema not loaded: ${schemaFile}`];
  }
  if (validate(data)) {
    return [];
  }
  return (validate.errors ?? []).map(
    (err: ErrorObject) =>
      `${artifactType}: ${err.instancePath || "/"} ${err.message ?? "invalid"}`,
  );
}
