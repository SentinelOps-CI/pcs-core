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
