"""Declarative release-profile engine for multi-domain PCS release-chain validation.

Profile-specific modules remain as compatibility wrappers that delegate here.
The engine is driven by ``ReleaseProfileSpec``: exact/optional artifact sets,
handoff completeness/order, status and commit requirements, certificate and
bundle-identity propagation, semantic validators, proof/import/payload/signature
requirements. Field bindings use JSON Pointer (RFC 6901).

Unknown workflow profiles fail closed with ``UnknownWorkflowProfile``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from pcs_core.bundle_identity import resolve_certified_bundle_identity_hash
from pcs_core.registry_data import registry_entries
from pcs_core.release_chain import ReleaseChainIssue, _issue
from pcs_core.release_chain_profiles import detect_workflow_profile_id
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

UNKNOWN_WORKFLOW_PROFILE = "UnknownWorkflowProfile"


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON Pointer against ``document``.

    Returns ``None`` when the pointer cannot be resolved. The empty pointer
    ``\"\"`` returns the document itself.
    """
    if pointer == "":
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return None
    current: Any = document
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                return None
            current = current[token]
        elif isinstance(current, list):
            try:
                index = int(token)
            except ValueError:
                return None
            if index < 0 or index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


@dataclass(frozen=True)
class CertificateIdBinding:
    """Declarative certificate-id / hash propagation requirement (JSON Pointer)."""

    source_artifact: str
    source_pointer: str
    target_artifact: str
    target_pointer: str
    mode: str = "equals"  # equals | array_contains
    issue_code: str = "certificate_id_mismatch"
    require_source: bool = True


@dataclass(frozen=True)
class StatusRequirement:
    artifact: str
    pointer: str
    required_value: Any
    issue_code: str
    skip_if_artifact_missing: bool = True


@dataclass(frozen=True)
class SourceCommitRequirement:
    """Require ``artifact#pointer`` equals ``manifest[manifest_commit_key]``."""

    artifact: str
    pointer: str
    manifest_commit_key: str
    issue_code: str


@dataclass(frozen=True)
class ProvenanceCommitRequirement:
    """Scan nested ``source_repo``/``source_commit`` pairs under an artifact."""

    artifact: str
    expected_repo: str
    manifest_commit_key: str
    issue_code: str
    nested_root_pointer: str = ""


@dataclass(frozen=True)
class BundleIdentityBinding:
    """Compare a field to the resolved certified-bundle identity hash."""

    artifact: str
    pointer: str
    issue_code: str
    require_present: bool = True
    missing_issue_code: str | None = None


@dataclass(frozen=True)
class ImportRequirement:
    artifact: str
    pointer: str
    required_value: Any
    issue_code: str


@dataclass(frozen=True)
class ProofRequirement:
    """Require a non-empty value at ``artifact#pointer``."""

    artifact: str
    pointer: str
    issue_code: str
    message: str | None = None


@dataclass(frozen=True)
class PayloadBinding:
    """Bind a declared digest (and optional size) to payload bytes under the release root."""

    artifact: str
    path_pointer: str
    digest_pointer: str
    issue_code: str = "payload_digest_mismatch"
    size_pointer: str | None = None
    size_issue_code: str = "payload_size_mismatch"
    missing_issue_code: str = "payload_missing"


@dataclass(frozen=True)
class SignatureRequirement:
    """Require a non-empty signature (or signature digest) field."""

    artifact: str
    pointer: str
    issue_code: str = "signature_missing"


@dataclass(frozen=True)
class ArrayElementBan:
    """Ban a value on each element of an array (e.g. rejected tool calls)."""

    artifact: str
    array_pointer: str
    element_pointer: str
    banned_value: Any
    issue_code: str
    message_template: str | None = None


@dataclass(frozen=True)
class ReleaseProfileSpec:
    """Declarative release-profile specification consumed by the engine."""

    workflow_profile_id: str
    required_artifacts: tuple[str, ...]
    optional_artifacts: tuple[str, ...] = ()
    release_pcs_artifacts: tuple[str, ...] = ()
    handoff_files: tuple[str, ...] = ()
    commit_keys: tuple[str, ...] = ()
    enforce_manifest_workflow_id: bool = True
    require_exact_manifest_artifact_set: bool = True
    handoff_require_complete: bool = False
    handoff_enforce_order: bool = True
    status_requirements: tuple[StatusRequirement, ...] = ()
    source_commit_requirements: tuple[SourceCommitRequirement, ...] = ()
    provenance_commit_requirements: tuple[ProvenanceCommitRequirement, ...] = ()
    certificate_bindings: tuple[CertificateIdBinding, ...] = ()
    bundle_identity_bindings: tuple[BundleIdentityBinding, ...] = ()
    import_requirements: tuple[ImportRequirement, ...] = ()
    proof_requirements: tuple[ProofRequirement, ...] = ()
    payload_bindings: tuple[PayloadBinding, ...] = ()
    signature_requirements: tuple[SignatureRequirement, ...] = ()
    array_element_bans: tuple[ArrayElementBan, ...] = ()
    domain_checks: DomainCheckFn | None = None
    semantic_validators: Mapping[str, Callable[[dict[str, Any]], list[str]]] = field(
        default_factory=dict,
    )
    semantic_issue_mapper: Callable[[str, str], str] | None = None
    alignment_checker: Callable[[Path, list[str]], None] | None = None
    alignment_issue_mapper: Callable[[str], str] | None = None
    # Retained only for side-by-side parity harnesses; production specs leave this None.
    legacy_validator: LegacyValidatorFn | None = None
    run_workflow_profile_declarations: bool = True

    @property
    def manifest_artifacts(self) -> tuple[str, ...]:
        """Backward-compatible alias for the required artifact set."""
        return self.required_artifacts


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


def normalized_issue_codes(issues: list[ReleaseChainIssue]) -> frozenset[str]:
    return frozenset(issue.code for issue in issues)


def compare_legacy_and_declarative(
    directory: Path,
    spec: ReleaseProfileSpec,
) -> tuple[frozenset[str], frozenset[str]]:
    """Return ``(legacy_codes, declarative_codes)`` for side-by-side parity."""
    if spec.legacy_validator is None:
        raise ValueError(
            f"profile {spec.workflow_profile_id!r} has no legacy_validator for parity",
        )
    base = directory.resolve()
    legacy_issues = list(spec.legacy_validator(base))
    declarative_spec = replace(spec, legacy_validator=None)
    declarative_issues = run_structural_release_profile_validation(base, declarative_spec)
    return normalized_issue_codes(legacy_issues), normalized_issue_codes(declarative_issues)


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
    if isinstance(handoff_sequence, list) and spec.handoff_files and spec.handoff_enforce_order:
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


def _repo_matches(repo: str, expected_repo: str) -> bool:
    return expected_repo.lower() in repo.lower()


def _iter_provenance_pairs(obj: Any) -> Any:
    if isinstance(obj, dict):
        repo = obj.get("source_repo")
        commit = obj.get("source_commit")
        if isinstance(repo, str) and isinstance(commit, str):
            yield repo, commit
        for value in obj.values():
            yield from _iter_provenance_pairs(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_provenance_pairs(item)


def _default_semantic_issue_code(artifact: str, message: str) -> str:
    if "missing_code_commit" in message or (
        "zero" in message and "commit" in message and "computation" in artifact
    ):
        return "missing_code_commit"
    if "exit_code" in message:
        return "nonzero_exit_code"
    return "schema_validation_failed"


def _default_alignment_issue_code(message: str) -> str:
    if "policy_hash" in message:
        return "policy_hash_mismatch"
    if "dataset_hash" in message:
        return "dataset_hash_mismatch"
    if "environment_hash" in message:
        return "environment_hash_mismatch"
    if "result_hashes" in message or "result_hash" in message:
        return "result_hash_mismatch"
    if "run_receipt_hash" in message:
        return "run_receipt_hash_mismatch"
    if "nonzero_exit_code" in message or "exit_code" in message:
        return "nonzero_exit_code"
    if "code_commit" in message:
        return "missing_code_commit"
    return "trace_hash_mismatch"


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

    required = set(spec.required_artifacts)
    optional = set(spec.optional_artifacts)
    allowed = required | optional
    present_keys = set(artifacts)

    if spec.require_exact_manifest_artifact_set:
        if optional:
            missing = sorted(required - present_keys)
            unexpected = sorted(present_keys - allowed)
        else:
            missing = sorted(required - present_keys)
            unexpected = sorted(present_keys - required)
        if missing:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    f"manifest artifacts missing keys: {missing}",
                ),
            )
        if unexpected:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    f"manifest artifacts unexpected keys: {unexpected}",
                ),
            )
    else:
        missing = sorted(required - present_keys)
        if missing:
            issues.append(
                _issue(
                    "schema_validation_failed",
                    f"manifest artifacts missing keys: {missing}",
                ),
            )

    check_names = sorted(present_keys & allowed) if optional else list(spec.required_artifacts)
    if not optional and spec.require_exact_manifest_artifact_set:
        check_names = list(spec.required_artifacts)

    for name in check_names:
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

    # Required artifacts not listed above (non-exact mode) still need presence checks.
    for name in spec.required_artifacts:
        if name in check_names:
            continue
        path = base / name
        if not path.is_file():
            issues.append(_issue("artifact_missing", f"missing artifact file {name}"))

    scan_errors: list[str] = []
    docs_to_scan = list(dict.fromkeys([*spec.required_artifacts, *check_names]))
    for name in docs_to_scan:
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
            mapper = spec.semantic_issue_mapper or _default_semantic_issue_code
            for msg in validator(doc):
                issues.append(_issue(mapper(name, msg), msg, artifact=name))
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
        mapper = spec.alignment_issue_mapper or _default_alignment_issue_code
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

    if spec.handoff_require_complete:
        for handoff_name in spec.handoff_files:
            if not (base / handoff_name).is_file():
                issues.append(
                    _issue(
                        "artifact_missing",
                        f"missing required handoff file {handoff_name}",
                        artifact=handoff_name,
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
        path = base / requirement.artifact
        if not path.is_file():
            if requirement.skip_if_artifact_missing:
                continue
            issues.append(
                _issue(
                    requirement.issue_code,
                    f"{requirement.artifact} missing for status requirement",
                    artifact=requirement.artifact,
                ),
            )
            continue
        doc = _load_json(path)
        if not isinstance(doc, dict):
            continue
        actual = resolve_json_pointer(doc, requirement.pointer)
        if actual != requirement.required_value:
            issues.append(
                _issue(
                    requirement.issue_code,
                    f"{requirement.artifact}{requirement.pointer} must be "
                    f"{requirement.required_value!r} (got {actual!r})",
                    artifact=requirement.artifact,
                    expected=requirement.required_value,
                    actual=actual,
                ),
            )

    for requirement in spec.source_commit_requirements:
        expected = commits.get(requirement.manifest_commit_key)
        if not isinstance(expected, str):
            continue
        doc = _load_json(base / requirement.artifact)
        if not isinstance(doc, dict):
            continue
        actual = resolve_json_pointer(doc, requirement.pointer)
        if actual != expected:
            issues.append(
                _issue(
                    requirement.issue_code,
                    f"{requirement.artifact}{requirement.pointer} {actual!r} "
                    f"!= manifest.{requirement.manifest_commit_key} {expected}",
                    artifact=requirement.artifact,
                    expected=expected,
                    actual=actual,
                ),
            )

    for requirement in spec.provenance_commit_requirements:
        expected = commits.get(requirement.manifest_commit_key)
        if not isinstance(expected, str):
            continue
        doc = _load_json(base / requirement.artifact)
        if not isinstance(doc, dict):
            continue
        root = (
            resolve_json_pointer(doc, requirement.nested_root_pointer)
            if requirement.nested_root_pointer
            else doc
        )
        if root is None:
            continue
        for repo, commit in _iter_provenance_pairs(root):
            if _repo_matches(repo, requirement.expected_repo) and commit != expected:
                issues.append(
                    _issue(
                        requirement.issue_code,
                        f"{requirement.artifact}: source_commit {commit} "
                        f"!= manifest.{requirement.manifest_commit_key} {expected}",
                        artifact=requirement.artifact,
                        expected=expected,
                        actual=commit,
                    ),
                )

    for binding in spec.certificate_bindings:
        source = _load_json(base / binding.source_artifact)
        target = _load_json(base / binding.target_artifact)
        if not isinstance(source, dict):
            continue
        expected = resolve_json_pointer(source, binding.source_pointer)
        if not isinstance(expected, str) or not expected:
            if binding.require_source:
                continue
            continue
        if not isinstance(target, dict):
            issues.append(
                _issue(
                    binding.issue_code,
                    f"{binding.target_artifact}{binding.target_pointer}: "
                    f"certificate ID is required",
                    artifact=binding.target_artifact,
                    expected=expected,
                ),
            )
            continue
        if binding.mode == "equals":
            actual = resolve_json_pointer(target, binding.target_pointer)
            if actual is None:
                issues.append(
                    _issue(
                        binding.issue_code,
                        f"{binding.target_artifact}{binding.target_pointer}: "
                        f"certificate ID is required",
                        artifact=binding.target_artifact,
                        expected=expected,
                    ),
                )
            elif actual != expected:
                issues.append(
                    _issue(
                        binding.issue_code,
                        f"{binding.target_artifact}{binding.target_pointer}: "
                        f"expected {expected!r}, got {actual!r}",
                        artifact=binding.target_artifact,
                        expected=expected,
                        actual=actual,
                    ),
                )
        elif binding.mode == "array_contains":
            refs = resolve_json_pointer(target, binding.target_pointer)
            if not isinstance(refs, list) or expected not in refs:
                issues.append(
                    _issue(
                        binding.issue_code,
                        f"{binding.target_artifact}{binding.target_pointer} "
                        f"must contain {expected!r}",
                        artifact=binding.target_artifact,
                        expected=expected,
                    ),
                )

    for requirement in spec.import_requirements:
        doc = _load_json(base / requirement.artifact)
        if not isinstance(doc, dict):
            continue
        actual = resolve_json_pointer(doc, requirement.pointer)
        if actual != requirement.required_value:
            issues.append(
                _issue(
                    requirement.issue_code,
                    f"{requirement.artifact}{requirement.pointer} must be "
                    f"{requirement.required_value!r} (got {actual!r})",
                    artifact=requirement.artifact,
                    expected=requirement.required_value,
                    actual=actual,
                ),
            )

    for requirement in spec.proof_requirements:
        doc = _load_json(base / requirement.artifact)
        if not isinstance(doc, dict):
            issues.append(
                _issue(
                    requirement.issue_code,
                    requirement.message
                    or f"{requirement.artifact}{requirement.pointer} is required",
                    artifact=requirement.artifact,
                ),
            )
            continue
        actual = resolve_json_pointer(doc, requirement.pointer)
        if actual is None or actual == "" or actual == {}:
            issues.append(
                _issue(
                    requirement.issue_code,
                    requirement.message
                    or f"{requirement.artifact}{requirement.pointer} is required",
                    artifact=requirement.artifact,
                ),
            )

    bundle_identity = resolve_certified_bundle_identity_hash(
        base,
        manifest_artifacts=artifacts if isinstance(artifacts, dict) else None,
    )
    for binding in spec.bundle_identity_bindings:
        if not bundle_identity:
            continue
        doc = _load_json(base / binding.artifact)
        if not isinstance(doc, dict):
            continue
        # When the pointer is nested, skip if the parent object is absent so
        # companion proof_requirements own the "missing parent" issue code.
        parent_pointer, _, _leaf = binding.pointer.rpartition("/")
        if parent_pointer:
            parent = resolve_json_pointer(doc, parent_pointer)
            if not isinstance(parent, dict):
                continue
        actual = resolve_json_pointer(doc, binding.pointer)
        if not actual:
            if binding.require_present:
                issues.append(
                    _issue(
                        binding.missing_issue_code or binding.issue_code,
                        f"{binding.artifact}{binding.pointer} is required",
                        artifact=binding.artifact,
                    ),
                )
            continue
        if actual != bundle_identity:
            issues.append(
                _issue(
                    binding.issue_code,
                    f"{binding.artifact}{binding.pointer} {actual} "
                    f"!= certified bundle identity hash {bundle_identity}",
                    artifact=binding.artifact,
                    expected=bundle_identity,
                    actual=actual,
                ),
            )

    for binding in spec.payload_bindings:
        doc = _load_json(base / binding.artifact)
        if not isinstance(doc, dict):
            continue
        rel_path = resolve_json_pointer(doc, binding.path_pointer)
        if not isinstance(rel_path, str) or not rel_path:
            continue
        from pcs_core.safe_paths import UnsafePathError, resolve_contained_file

        try:
            payload_path = resolve_contained_file(base, rel_path)
        except UnsafePathError as exc:
            message = str(exc).lower()
            if "does not resolve" in message or "not a regular file" in message:
                code = binding.missing_issue_code
            else:
                code = "payload_path_unsafe"
            issues.append(
                _issue(
                    code,
                    f"{binding.artifact}{binding.path_pointer}: {exc}",
                    artifact=binding.artifact,
                ),
            )
            continue
        payload_bytes = payload_path.read_bytes()
        actual_digest = file_digest(payload_bytes)
        expected_digest = resolve_json_pointer(doc, binding.digest_pointer)
        if expected_digest != actual_digest:
            issues.append(
                _issue(
                    binding.issue_code,
                    f"{binding.artifact}{binding.digest_pointer}: expected {expected_digest}, "
                    f"got {actual_digest}",
                    artifact=binding.artifact,
                    expected=expected_digest,
                    actual=actual_digest,
                ),
            )
        if binding.size_pointer:
            expected_size = resolve_json_pointer(doc, binding.size_pointer)
            actual_size = len(payload_bytes)
            if expected_size != actual_size:
                issues.append(
                    _issue(
                        binding.size_issue_code,
                        f"{binding.artifact}{binding.size_pointer}: expected {expected_size}, "
                        f"got {actual_size}",
                        artifact=binding.artifact,
                        expected=expected_size,
                        actual=actual_size,
                    ),
                )

    for requirement in spec.signature_requirements:
        doc = _load_json(base / requirement.artifact)
        if not isinstance(doc, dict):
            continue
        actual = resolve_json_pointer(doc, requirement.pointer)
        if actual is None or actual == "":
            issues.append(
                _issue(
                    requirement.issue_code,
                    f"{requirement.artifact}{requirement.pointer} signature is required",
                    artifact=requirement.artifact,
                ),
            )

    for ban in spec.array_element_bans:
        doc = _load_json(base / ban.artifact)
        if not isinstance(doc, dict):
            continue
        array = resolve_json_pointer(doc, ban.array_pointer)
        if not isinstance(array, list):
            continue
        for index, element in enumerate(array):
            if not isinstance(element, dict):
                continue
            value = resolve_json_pointer(element, ban.element_pointer)
            if value == ban.banned_value:
                message = ban.message_template or (
                    f"{ban.artifact}{ban.array_pointer}/{index}{ban.element_pointer} "
                    f"is {ban.banned_value!r}"
                )
                if ban.message_template and "{index}" in ban.message_template:
                    message = ban.message_template.format(index=index)
                issues.append(_issue(ban.issue_code, message, artifact=ban.artifact))

    if spec.domain_checks is not None:
        spec.domain_checks(base, manifest, commits, issues)

    return issues


def run_release_profile_validation(
    directory: Path,
    spec: ReleaseProfileSpec,
) -> list[ReleaseChainIssue]:
    """Run release-profile validation for ``spec``.

    When ``legacy_validator`` is set (parity harness only), that body remains the
    comparison source of truth. Production profiles leave it unset and run the
    declarative pipeline alone.
    """
    base = directory.resolve()
    if spec.legacy_validator is not None:
        issues = list(spec.legacy_validator(base))
        if spec.run_workflow_profile_declarations:
            validate_workflow_profile_declarations(base, spec, issues)
        return issues
    return run_structural_release_profile_validation(base, spec)


def validate_release_directory(directory: Path) -> list[ReleaseChainIssue]:
    """Detect profile and run the declarative engine; unknown profiles fail closed."""
    # Ensure specs are registered.
    import pcs_core.release_profile_specs  # noqa: F401

    base = directory.resolve()
    workflow_id = detect_workflow_profile_id(base)
    if workflow_id is None:
        if not (base / MANIFEST_NAME).is_file():
            return [
                _issue("manifest_missing", f"{MANIFEST_NAME} not found in {base}"),
            ]
        return [
            _issue(
                UNKNOWN_WORKFLOW_PROFILE,
                "unable to detect workflow profile for release directory",
            ),
        ]
    spec = get_release_profile(workflow_id)
    if spec is None:
        return [
            _issue(
                UNKNOWN_WORKFLOW_PROFILE,
                f"unknown workflow profile {workflow_id!r}",
                actual=workflow_id,
            ),
        ]
    return run_release_profile_validation(base, spec)
