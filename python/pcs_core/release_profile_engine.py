"""Declarative release-profile engine for multi-domain PCS release-chain validation.

Profile-specific modules remain as compatibility wrappers that delegate here.
The engine is driven by ``ReleaseProfileSpec`` (artifact/commit/handoff registries)
plus ``WorkflowProfile.v0`` metadata (handoff sequence, required registry entries,
status policy). Domain validators may still run via ``legacy_validator`` until
their checks are fully expressed as declarative bindings.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pcs_core.registry_data import registry_entries
from pcs_core.release_chain import ReleaseChainIssue, _issue
from pcs_core.release_chain_profiles import (
    LABTRUST_WORKFLOW_PROFILE_ID,
    detect_workflow_profile_id,
)
from pcs_core.release_fixtures import (
    MANIFEST_NAME,
    _load_json,
    _scan_forbidden_values,
    file_digest,
    is_release_pattern_placeholder,
    is_zero_commit,
)
from pcs_core.status_policy import FORBIDDEN_TRANSITIONS
from pcs_core.validate import ValidationError, validate_file
from pcs_core.workflow_profiles import load_workflow_profile

LegacyValidatorFn = Callable[[Path], list[ReleaseChainIssue]]
DomainCheckFn = Callable[
    [Path, dict[str, Any], dict[str, Any], list[ReleaseChainIssue]],
    None,
]


@dataclass(frozen=True)
class CertificateIdBinding:
    """Declarative certificate-id / hash propagation requirement."""

    source_artifact: str
    source_field: str
    target_artifact: str
    target_field: str
    mode: str = "equals"  # equals | ref_contains


@dataclass(frozen=True)
class StatusRequirement:
    artifact: str
    field: str
    required_value: str
    issue_code: str


@dataclass(frozen=True)
class ReleaseProfileSpec:
    """Declarative release-profile specification consumed by the engine."""

    workflow_profile_id: str
    manifest_artifacts: tuple[str, ...]
    release_pcs_artifacts: tuple[str, ...]
    handoff_files: tuple[str, ...]
    commit_keys: tuple[str, ...]
    enforce_manifest_workflow_id: bool = True
    require_exact_manifest_artifact_set: bool = True
    status_requirements: tuple[StatusRequirement, ...] = ()
    certificate_bindings: tuple[CertificateIdBinding, ...] = ()
    domain_checks: DomainCheckFn | None = None
    semantic_validators: Mapping[str, Callable[[dict[str, Any]], list[str]]] = field(
        default_factory=dict,
    )
    alignment_checker: Callable[[Path, list[str]], None] | None = None
    alignment_issue_mapper: Callable[[str], str] | None = None
    # Until full declarative parity is proven, run the battle-tested validator body.
    legacy_validator: LegacyValidatorFn | None = None
    run_workflow_profile_declarations: bool = True


_PROFILE_REGISTRY: dict[str, ReleaseProfileSpec] = {}


def register_release_profile(spec: ReleaseProfileSpec) -> ReleaseProfileSpec:
    _PROFILE_REGISTRY[spec.workflow_profile_id] = spec
    return spec


def get_release_profile(workflow_profile_id: str) -> ReleaseProfileSpec | None:
    return _PROFILE_REGISTRY.get(workflow_profile_id)


def list_release_profiles() -> tuple[ReleaseProfileSpec, ...]:
    return tuple(_PROFILE_REGISTRY.values())


def resolve_release_profile(directory: Path) -> ReleaseProfileSpec | None:
    workflow_id = detect_workflow_profile_id(directory.resolve())
    if workflow_id and workflow_id in _PROFILE_REGISTRY:
        return _PROFILE_REGISTRY[workflow_id]
    return None


def validate_workflow_profile_declarations(
    base: Path,
    spec: ReleaseProfileSpec,
    issues: list[ReleaseChainIssue],
) -> dict[str, Any] | None:
    """Enforce WorkflowProfile.v0 handoff sequence + registry entry declarations."""
    profile = load_workflow_profile(spec.workflow_profile_id)
    if profile is None:
        issues.append(
            _issue(
                "schema_validation_failed",
                f"WorkflowProfile.v0 not found for {spec.workflow_profile_id}",
            ),
        )
        return None

    handoff_sequence = profile.get("handoff_sequence")
    if isinstance(handoff_sequence, list) and spec.handoff_files:
        expected = [str(item) for item in handoff_sequence if isinstance(item, str)]
        expected_index = {kind: index for index, kind in enumerate(expected)}
        # Prefer HandoffManifest.v0 files for sequence ordering; legacy handoff_to_*.json
        # may duplicate kinds out of order.
        manifest_kinds: list[str] = []
        for handoff_name in spec.handoff_files:
            if not str(handoff_name).startswith("handoff_manifest."):
                continue
            path = base / handoff_name
            if not path.is_file():
                continue
            doc = _load_json(path)
            if not isinstance(doc, dict):
                continue
            kind = doc.get("handoff_kind")
            if isinstance(kind, str) and kind:
                if kind not in expected:
                    issues.append(
                        _issue(
                            "schema_validation_failed",
                            f"{handoff_name}: handoff_kind {kind!r} not in "
                            f"WorkflowProfile.v0.handoff_sequence",
                            artifact=handoff_name,
                        ),
                    )
                    continue
                manifest_kinds.append(kind)
        # Relative order of first occurrences must follow the profile sequence.
        seen: list[str] = []
        for kind in manifest_kinds:
            if kind not in seen:
                seen.append(kind)
        if seen != sorted(seen, key=lambda kind: expected_index.get(kind, 10_000)):
            issues.append(
                _issue(
                    "schema_validation_failed",
                    "handoff_manifest sequence order mismatch against WorkflowProfile.v0: "
                    f"expected order {sorted(seen, key=lambda k: expected_index[k])}, "
                    f"got {seen}",
                ),
            )

    required_entries = profile.get("required_registry_entries")
    if isinstance(required_entries, list):
        known = set(registry_entries().keys())
        for entry in required_entries:
            if not isinstance(entry, str):
                continue
            if entry not in known:
                issues.append(
                    _issue(
                        "schema_validation_failed",
                        f"WorkflowProfile required_registry_entries references unknown "
                        f"artifact type {entry!r}",
                    ),
                )

    status_policy = profile.get("status_policy")
    if isinstance(status_policy, dict):
        forbidden = status_policy.get("forbidden_transitions")
        if isinstance(forbidden, list):
            for item in forbidden:
                if not isinstance(item, dict):
                    continue
                pair = (item.get("from_status"), item.get("to_status"))
                if pair[0] and pair[1] and pair not in FORBIDDEN_TRANSITIONS:
                    issues.append(
                        _issue(
                            "schema_validation_failed",
                            "WorkflowProfile status_policy.forbidden_transitions entry "
                            f"{pair} is not present in global status_policy table",
                        ),
                    )

    return profile


def _read_field(doc: dict[str, Any], dotted_or_simple: str) -> Any:
    if "." not in dotted_or_simple and "[" not in dotted_or_simple:
        return doc.get(dotted_or_simple)
    if dotted_or_simple == "certificates[0].certificate_id":
        certs = doc.get("certificates")
        if isinstance(certs, list) and certs and isinstance(certs[0], dict):
            return certs[0].get("certificate_id")
        return None
    if dotted_or_simple.startswith("verified_input."):
        verified = doc.get("verified_input")
        if isinstance(verified, dict):
            return verified.get(dotted_or_simple.split(".", 1)[1])
        return None
    current: Any = doc
    for part in dotted_or_simple.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def run_structural_release_profile_validation(
    directory: Path,
    spec: ReleaseProfileSpec,
) -> list[ReleaseChainIssue]:
    """Run the declarative structural pipeline (no legacy validator)."""
    issues: list[ReleaseChainIssue] = []
    base = directory.resolve()

    manifest_path = base / MANIFEST_NAME
    if not manifest_path.is_file():
        issues.append(_issue("manifest_missing", f"{MANIFEST_NAME} not found in {base}"))
        return issues

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(_issue("schema_validation_failed", f"manifest JSON parse error: {exc}"))
        return issues

    if not isinstance(manifest, dict):
        issues.append(_issue("schema_validation_failed", "manifest root must be a JSON object"))
        return issues

    if spec.enforce_manifest_workflow_id:
        profile_id = manifest.get("workflow_profile_id")
        if profile_id != spec.workflow_profile_id:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    f"manifest workflow_profile_id must be {spec.workflow_profile_id!r}",
                    actual=profile_id,
                ),
            )

    commits = {key: manifest.get(key) for key in spec.commit_keys}
    for key in spec.commit_keys:
        commit = commits[key]
        if not isinstance(commit, str) or len(commit) != 40:
            issues.append(_issue("schema_validation_failed", f"manifest missing or invalid {key}"))
        elif is_zero_commit(commit):
            issues.append(
                _issue(
                    "placeholder_commit_detected",
                    f"manifest {key} uses zero provenance: {commit}",
                    artifact=MANIFEST_NAME,
                ),
            )
        elif is_release_pattern_placeholder(commit):
            issues.append(
                _issue(
                    "placeholder_commit_detected",
                    f"manifest {key} uses pattern placeholder provenance: {commit}",
                    artifact=MANIFEST_NAME,
                ),
            )

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        issues.append(_issue("schema_validation_failed", "manifest artifacts must be an object"))
        return issues

    if spec.require_exact_manifest_artifact_set:
        if set(artifacts) != set(spec.manifest_artifacts):
            missing = sorted(set(spec.manifest_artifacts) - set(artifacts))
            extra = sorted(set(artifacts) - set(spec.manifest_artifacts))
            if missing:
                issues.append(
                    _issue(
                        "schema_validation_failed",
                        f"manifest artifacts missing keys: {missing}",
                    ),
                )
            if extra:
                issues.append(
                    _issue(
                        "schema_validation_failed",
                        f"manifest artifacts unexpected keys: {extra}",
                    ),
                )

    for name in spec.manifest_artifacts:
        path = base / name
        if not path.is_file():
            issues.append(_issue("artifact_missing", f"missing artifact file {name}"))
            continue
        expected = artifacts.get(name)
        actual = file_digest(path.read_bytes())
        if expected != actual:
            issues.append(
                _issue(
                    "manifest_hash_mismatch",
                    f"{name}: manifest digest mismatch (expected {expected}, got {actual})",
                    artifact=name,
                    expected=expected,
                    actual=actual,
                ),
            )

    scan_errors: list[str] = []
    for name in spec.manifest_artifacts:
        path = base / name
        if not path.is_file():
            continue
        doc = _load_json(path)
        if doc is None:
            issues.append(
                _issue("schema_validation_failed", f"{name}: invalid JSON", artifact=name),
            )
            continue
        validator = spec.semantic_validators.get(name)
        if validator is not None:
            for msg in validator(doc):
                issues.append(_issue("schema_validation_failed", msg, artifact=name))
        _scan_forbidden_values(doc, label=name, errors=scan_errors)
    for msg in scan_errors:
        artifact = msg.split(":", 1)[0] if ":" in msg else None
        if "local_dev" in msg:
            issues.append(_issue("local_dev_detected", msg, artifact=artifact))
        elif "zero" in msg or "placeholder" in msg:
            issues.append(_issue("placeholder_commit_detected", msg, artifact=artifact))
        else:
            issues.append(_issue("schema_validation_failed", msg, artifact=artifact))

    if spec.alignment_checker is not None:
        alignment_errors: list[str] = []
        spec.alignment_checker(base, alignment_errors)
        mapper = spec.alignment_issue_mapper or (lambda _msg: "trace_hash_mismatch")
        for msg in alignment_errors:
            issues.append(_issue(mapper(msg), msg))

    for name in spec.release_pcs_artifacts:
        path = base / name
        if not path.is_file():
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    f"{name}: pcs validate failed: {exc}",
                    artifact=name,
                ),
            )

    for handoff_name in spec.handoff_files:
        handoff_path = base / handoff_name
        if handoff_path.is_file():
            try:
                validate_file(handoff_path)
            except ValidationError as exc:
                issues.append(
                    _issue(
                        "schema_validation_failed",
                        f"{handoff_name}: pcs validate failed: {exc}",
                        artifact=handoff_name,
                    ),
                )

    if spec.run_workflow_profile_declarations:
        validate_workflow_profile_declarations(base, spec, issues)

    for requirement in spec.status_requirements:
        doc = _load_json(base / requirement.artifact)
        if not isinstance(doc, dict):
            continue
        actual = _read_field(doc, requirement.field)
        if actual != requirement.required_value:
            issues.append(
                _issue(
                    requirement.issue_code,
                    f"{requirement.artifact}.{requirement.field} must be "
                    f"{requirement.required_value!r} (got {actual!r})",
                    artifact=requirement.artifact,
                    expected=requirement.required_value,
                    actual=actual,
                ),
            )

    for binding in spec.certificate_bindings:
        source = _load_json(base / binding.source_artifact)
        target = _load_json(base / binding.target_artifact)
        if not isinstance(source, dict) or not isinstance(target, dict):
            continue
        expected = _read_field(source, binding.source_field)
        if not isinstance(expected, str) or not expected:
            continue
        if binding.mode == "equals":
            actual = _read_field(target, binding.target_field)
            if actual != expected:
                issues.append(
                    _issue(
                        "certificate_id_mismatch",
                        f"{binding.target_artifact}.{binding.target_field}: "
                        f"expected {expected!r}, got {actual!r}",
                        artifact=binding.target_artifact,
                        expected=expected,
                        actual=actual,
                    ),
                )
        elif binding.mode == "ref_contains":
            from pcs_core.release_chain import _certificate_ref_contains

            if not _certificate_ref_contains(target, binding.target_field, expected):
                issues.append(
                    _issue(
                        "certificate_id_mismatch",
                        f"{binding.target_artifact}.{binding.target_field}.certificate_refs "
                        f"must contain {expected!r}",
                        artifact=binding.target_artifact,
                        expected=expected,
                    ),
                )

    if spec.domain_checks is not None:
        spec.domain_checks(base, manifest, commits, issues)

    return issues


def run_release_profile_validation(
    directory: Path,
    spec: ReleaseProfileSpec,
) -> list[ReleaseChainIssue]:
    """Run release-profile validation for ``spec``.

    When ``legacy_validator`` is set, that body remains the source of truth for
    parity; WorkflowProfile declaration checks are still applied on top.
    """
    base = directory.resolve()
    if spec.legacy_validator is not None:
        issues = list(spec.legacy_validator(base))
        if spec.run_workflow_profile_declarations:
            validate_workflow_profile_declarations(base, spec, issues)
        return issues
    return run_structural_release_profile_validation(base, spec)


def validate_release_directory(directory: Path) -> list[ReleaseChainIssue]:
    """Detect profile and run the declarative engine (LabTrust default)."""
    # Ensure specs are registered.
    import pcs_core.release_profile_specs  # noqa: F401

    spec = resolve_release_profile(directory)
    if spec is None:
        spec = get_release_profile(LABTRUST_WORKFLOW_PROFILE_ID)
    if spec is None:
        return [
            _issue(
                "schema_validation_failed",
                "no release profile registered for directory",
            ),
        ]
    return run_release_profile_validation(directory, spec)
