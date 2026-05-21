/** Semantic validation for PcsBenchIngest.v0 / BenchmarkArtifactRef.v0 (parity with pcs_core.benchmark_validate). */

const INGEST_EMBEDDED_ARRAYS: Record<string, string> = {
  "BenchmarkRun.v0": "benchmark_runs",
  "CoverageReport.v0": "coverage_reports",
  "FailureLocalizationResult.v0": "failure_localization_reports",
  "ExplainQualityReport.v0": "explain_quality_reports",
  "ProfileCoverageReport.v0": "profile_coverage_reports",
};

const PRODUCER_EMBEDDED_REF_FIELDS: Record<string, readonly string[]> = {
  "labtrust-gym": ["benchmark_runs"],
  certifyedge: ["coverage_reports"],
  "provability-fabric": ["explain_quality_reports", "profile_coverage_reports"],
  "scientific-memory": ["explain_quality_reports"],
};

const ALLOWED_PRODUCERS = new Set([
  "pcs-core",
  "pcs-bench",
  "labtrust-gym",
  "certifyedge",
  "provability-fabric",
  "scientific-memory",
]);

function embeddedObjects(
  data: Record<string, unknown>,
  artifactType: string,
): Record<string, unknown>[] {
  const field = INGEST_EMBEDDED_ARRAYS[artifactType];
  if (!field) return [];
  const rows = data[field];
  if (!Array.isArray(rows)) return [];
  return rows.filter((row): row is Record<string, unknown> => !!row && typeof row === "object");
}

export function validateBenchmarkArtifactRefSemantics(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  const artifactType = data.artifact_type;
  if (typeof artifactType !== "string" || !(artifactType in INGEST_EMBEDDED_ARRAYS)) {
    errors.push(`BenchmarkArtifactRef.v0 unsupported artifact_type ${String(artifactType)}`);
  }
  const path = data.path;
  if (typeof path !== "string" || !path.trim()) {
    errors.push("BenchmarkArtifactRef.v0 path must be non-empty");
  }
  const sha256 = data.sha256;
  if (typeof sha256 === "string" && !sha256.startsWith("sha256:")) {
    errors.push("BenchmarkArtifactRef.v0 sha256 must be a sha256: hex digest");
  }
  return errors;
}

export function validatePcsBenchIngestSemantics(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  const producerId = data.producer_id;
  if (typeof producerId !== "string" || !ALLOWED_PRODUCERS.has(producerId)) {
    errors.push(`PcsBenchIngest.v0 unknown producer_id ${String(producerId)}`);
  }
  for (const field of [
    "benchmark_runs",
    "coverage_reports",
    "failure_localization_reports",
    "explain_quality_reports",
    "profile_coverage_reports",
    "commands",
    "logs",
  ]) {
    if (!Array.isArray(data[field])) {
      errors.push(`PcsBenchIngest.v0 requires list ${field}`);
    }
  }

  const producerFields = PRODUCER_EMBEDDED_REF_FIELDS[String(producerId)] ?? [];
  const hasProducerEmbedded = producerFields.some((field) => {
    const rows = data[field];
    return Array.isArray(rows) && rows.length > 0;
  });

  const refs = data.artifact_refs;
  if (hasProducerEmbedded && refs === undefined) {
    errors.push(
      `PcsBenchIngest.v0 producer ${String(producerId)} requires artifact_refs when exporting embedded artifacts`,
    );
    return errors;
  }
  if (refs === undefined) {
    return errors;
  }
  if (!Array.isArray(refs)) {
    errors.push("PcsBenchIngest.v0 artifact_refs must be an array when present");
    return errors;
  }

  const paths: string[] = [];
  const refKeys = new Set<string>();
  refs.forEach((ref, index) => {
    if (!ref || typeof ref !== "object") {
      errors.push(`artifact_refs[${index}] must be an object`);
      return;
    }
    const row = ref as Record<string, unknown>;
    for (const msg of validateBenchmarkArtifactRefSemantics(row)) {
      errors.push(`artifact_refs[${index}]: ${msg}`);
    }
    const artifactType = String(row.artifact_type ?? "");
    const sha256 = row.sha256;
    const path = row.path;
    if (typeof path === "string") {
      paths.push(path);
    }
    const embedded = embeddedObjects(data, artifactType);
    if (embedded.length === 0) {
      errors.push(`artifact_refs[${index}]: no embedded objects for ${artifactType}`);
      return;
    }
    if (
      typeof sha256 === "string" &&
      !embedded.some((item) => item.signature_or_digest === sha256)
    ) {
      errors.push(
        `artifact_refs[${index}]: sha256 does not match any embedded ${artifactType} signature_or_digest`,
      );
    } else if (typeof sha256 === "string") {
      refKeys.add(`${artifactType}\0${sha256}`);
    }
  });

  if (paths.length !== new Set(paths).size) {
    errors.push("PcsBenchIngest.v0 artifact_refs contains duplicate path values");
  }

  if (hasProducerEmbedded) {
    for (const field of producerFields) {
      const rows = data[field];
      if (!Array.isArray(rows)) continue;
      const artifactType = Object.entries(INGEST_EMBEDDED_ARRAYS).find(
        ([, fname]) => fname === field,
      )?.[0];
      if (!artifactType) continue;
      rows.forEach((row, rowIndex) => {
        if (!row || typeof row !== "object") return;
        const digest = (row as Record<string, unknown>).signature_or_digest;
        if (typeof digest === "string" && !refKeys.has(`${artifactType}\0${digest}`)) {
          errors.push(
            `${field}[${rowIndex}]: missing artifact_refs entry for ${artifactType} digest ${digest}`,
          );
        }
      });
    }
  }

  return errors;
}
