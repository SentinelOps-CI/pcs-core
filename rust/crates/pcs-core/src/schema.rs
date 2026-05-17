use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use jsonschema::{Resource, Validator};
use serde_json::Value;

use crate::validation::ValidationError;

fn schemas_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .join("schemas")
}

fn schema_options() -> jsonschema::ValidationOptions {
    static OPTIONS: OnceLock<jsonschema::ValidationOptions> = OnceLock::new();
    OPTIONS
        .get_or_init(|| {
            let mut options = jsonschema::draft202012::options();
            let dir = schemas_dir();
            for entry in std::fs::read_dir(&dir).expect("schemas directory readable") {
                let path = entry.expect("schema dir entry").path();
                if path.extension().and_then(|s| s.to_str()) != Some("json") {
                    continue;
                }
                let content = std::fs::read_to_string(&path).expect("schema file readable");
                let schema: Value =
                    serde_json::from_str(&content).expect("schema file is valid JSON");
                let file_name = path.file_name().unwrap().to_string_lossy().to_string();
                let resource =
                    Resource::from_contents(schema.clone()).expect("schema resource construction");
                options.with_resource(&file_name, resource);
                if let Some(id) = schema.get("$id").and_then(|v| v.as_str()) {
                    let resource = Resource::from_contents(schema.clone())
                        .expect("schema resource construction");
                    options.with_resource(id, resource);
                }
            }
            options
        })
        .clone()
}

pub fn compile_schema(schema_name: &str) -> Result<Validator, ValidationError> {
    let path = schemas_dir().join(schema_name);
    let schema: Value =
        serde_json::from_str(
            &std::fs::read_to_string(&path).map_err(|e| ValidationError {
                message: format!("read schema {schema_name}: {e}"),
            })?,
        )
        .map_err(|e| ValidationError {
            message: format!("parse schema {schema_name}: {e}"),
        })?;
    schema_options()
        .build(&schema)
        .map_err(|e| ValidationError {
            message: format!("compile schema {schema_name}: {e}"),
        })
}

pub fn validate_schema(
    compiled: &Validator,
    value: &Value,
    label: &str,
) -> Result<(), ValidationError> {
    if compiled.is_valid(value) {
        return Ok(());
    }
    let messages: Vec<String> = compiled
        .iter_errors(value)
        .map(|err| format!("{label}: {err}"))
        .collect();
    Err(ValidationError {
        message: messages.join("; "),
    })
}
