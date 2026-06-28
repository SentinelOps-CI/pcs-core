"""PF-Core semantic validation and fixture harness."""

import json
from pathlib import Path
from typing import Any

from pcs_core.paths import repo_root
from pcs_core.registry_data import (
    PF_CORE_CERTIFICATE_CLAIM_CLASSES,
    PF_CORE_CLAIM_CLASSES,
    PF_CORE_TRACE_CLAIM_CLASSES,
)
from pcs_core.validate_detect import ARTIFACT_SCHEMAS, ValidationError, detect_artifact_type

_PF_CORE_ARTIFACT_TYPES = frozenset(
    key for key in ARTIFACT_SCHEMAS if key.startswith("PFCore") or key == "ToolUseTrace.v0"
)

LEAN_CHECK_RESULT_STATUSES = frozenset(
    {
        "DecidersPassed",
        "LeanProofChecked",
        "ReplayValidated",
        "Rejected",
        "Stale",
    }
)


def _validate_pfcore_claim_class(
    data: dict[str, Any],
    path: str,
    errors: list[str],
    *,
    allowed: frozenset[str],
    artifact_kind: str,
) -> None:
    claim_class = data.get("claim_class")
    if not isinstance(claim_class, str):
        return
    if claim_class not in allowed:
        if artifact_kind == "trace" and claim_class in {"LeanKernelChecked", "CertificateChecked"}:
            errors.append(
                f"{path}: claim_class {claim_class!r} is not valid on PFCoreTrace.v0 "
                f"(use PFCoreCertificate.v0 for kernel or external checker claims)"
            )
        else:
            errors.append(f"{path}: invalid claim_class {claim_class!r} for {artifact_kind}")
        return
    if claim_class == "LeanKernelChecked" and not data.get("proof_ref"):
        errors.append(
            f"{path}: claim_class LeanKernelChecked requires proof_ref (ClaimClassOverclaim)"
        )
    if claim_class == "LeanKernelChecked" and not data.get("proof_term_ref"):
        errors.append(
            f"{path}: claim_class LeanKernelChecked requires proof_term_ref (ClaimClassOverclaim)"
        )
    if claim_class == "LeanKernelChecked" and data.get("lean_proof_checked") is not True:
        errors.append(f"{path}: claim_class LeanKernelChecked requires lean_proof_checked=true")


def _validate_direct_trace_action_semantics(trace: dict[str, Any]) -> list[str]:
    from pcs_core.pf_core_runtime import (
        validate_action_capabilities_known,
        validate_action_capability_effects,
        validate_action_effects_known,
    )

    errors: list[str] = []
    events = trace.get("events")
    if not isinstance(events, list):
        return errors
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        action = event.get("action")
        if not isinstance(action, dict):
            continue
        base = f"events[{index}].action"
        try:
            validate_action_effects_known(action, path=base)
        except Exception as exc:
            code = getattr(exc, "code", "UnknownEffect")
            message = str(exc)
            path = getattr(exc, "path", base)
            errors.append(f"{code}: {message} (at {path})")
        try:
            validate_action_capabilities_known(action, path=base)
        except Exception as exc:
            code = getattr(exc, "code", "UnknownCapability")
            message = str(exc)
            path = getattr(exc, "path", base)
            errors.append(f"{code}: {message} (at {path})")
        try:
            validate_action_capability_effects(action, path=base)
        except Exception as exc:
            code = getattr(exc, "code", "CapabilityEffectMismatch")
            message = str(exc)
            path = getattr(exc, "path", base)
            errors.append(f"{code}: {message} (at {path})")
    return errors


def _validate_pfcore_trace(data: dict[str, Any]) -> list[str]:
    from pcs_core.pf_core_contract import validate_trace_contract_binding
    from pcs_core.pf_core_runtime import validate_pfcore_trace_hash_chain

    errors: list[str] = []
    _validate_pfcore_claim_class(
        data, "root", errors, allowed=PF_CORE_TRACE_CLAIM_CLASSES, artifact_kind="trace"
    )
    errors.extend(_validate_direct_trace_action_semantics(data))
    errors.extend(validate_trace_contract_binding(data))
    errors.extend(validate_pfcore_trace_hash_chain(data))
    return errors


def _validate_pfcore_certificate(data: dict[str, Any]) -> list[str]:
    from pcs_core.lean_catalog import PF_CORE_CONCRETE_PROOF_THEOREMS
    from pcs_core.pf_core_contract import DEFAULT_TRACE_SAFE_CONTRACT_ID
    from pcs_core.registry_data import enforce_assumption_declared, registry_entries

    errors: list[str] = []
    _validate_pfcore_claim_class(
        data, "root", errors, allowed=PF_CORE_CERTIFICATE_CLAIM_CLASSES, artifact_kind="certificate"
    )
    claim_class = data.get("claim_class")
    lean_proof_checked = data.get("lean_proof_checked") is True
    if lean_proof_checked and not data.get("proof_term_ref"):
        errors.append("root: lean_proof_checked requires proof_term_ref")
    if lean_proof_checked or claim_class == "LeanKernelChecked":
        proof_term_hash = data.get("proof_term_hash")
        if not isinstance(proof_term_hash, str) or not proof_term_hash.startswith("sha256:"):
            errors.append("root: claim_class LeanKernelChecked requires proof_term_hash")
    if lean_proof_checked:
        build = data.get("lean_build_status")
        if not isinstance(build, dict) or build.get("ok") is not True:
            errors.append("root: lean_proof_checked requires lean_build_status.ok=true")
        theorems = data.get("theorems_checked")
        if isinstance(theorems, list):
            theorem_set = {str(item) for item in theorems}
            missing = PF_CORE_CONCRETE_PROOF_THEOREMS - theorem_set
            if missing:
                errors.append(
                    f"root: lean_proof_checked theorems_checked missing {sorted(missing)!r}"
                )
        obligations = data.get("obligations")
        if isinstance(obligations, list):
            required = {
                "concrete_trace_safe",
                "concrete_trace_safe_prop",
                "concrete_allowed_events_allowed",
            }
            passed = {
                str(item.get("theorem"))
                for item in obligations
                if isinstance(item, dict) and item.get("passed") is True
            }
            missing_obligations = required - passed
            if missing_obligations:
                errors.append(
                    "root: lean_proof_checked obligations missing passed proofs for "
                    f"{sorted(missing_obligations)!r}"
                )
    if claim_class == "LeanKernelChecked" and not lean_proof_checked:
        errors.append("root: claim_class LeanKernelChecked requires lean_proof_checked=true")
    if claim_class == "LeanKernelChecked":
        env_hash = data.get("lean_environment_hash")
        if not isinstance(env_hash, str) or not env_hash.startswith("sha256:"):
            errors.append("root: claim_class LeanKernelChecked requires lean_environment_hash")
        default_ref = str(data.get("default_contract_ref") or "")
        semantics = data.get("contract_semantics_checked")
        has_semantics = isinstance(semantics, dict) and (
            bool(semantics.get("lean")) or bool(semantics.get("runtime"))
        )
        if default_ref != DEFAULT_TRACE_SAFE_CONTRACT_ID and not has_semantics:
            errors.append(
                "root: claim_class LeanKernelChecked requires contract_refs or "
                f"default_contract_ref {DEFAULT_TRACE_SAFE_CONTRACT_ID!r}"
            )
    errors.extend(enforce_assumption_declared(data, registry_entries().get("PFCoreCertificate.v0")))
    return errors


def _validate_lean_check_result(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    claim_class = data.get("claim_class")
    if isinstance(claim_class, str) and claim_class not in PF_CORE_CLAIM_CLASSES:
        errors.append(f"root: invalid claim_class {claim_class!r}")
    status = str(data.get("status") or "")
    lean_proof_checked = data.get("lean_proof_checked") is True
    if status == "LeanProofChecked" and claim_class != "LeanKernelChecked":
        errors.append("root: status LeanProofChecked requires claim_class LeanKernelChecked")
    if status == "ReplayValidated" and claim_class != "ReplayValidated":
        obligations = data.get("obligations")
        boundary_ok = isinstance(obligations, list) and any(
            isinstance(item, dict)
            and item.get("theorem") == "replay_preserves_claim_boundary"
            and item.get("passed") is True
            for item in obligations
        )
        if not (data.get("replay_match") is True and boundary_ok):
            errors.append(
                "root: status ReplayValidated requires claim_class ReplayValidated "
                "unless replay_preserves_claim_boundary holds with replay_match"
            )
    if status == "LeanProofChecked" and not lean_proof_checked:
        errors.append("root: status LeanProofChecked requires lean_proof_checked=true")
    if claim_class == "LeanKernelChecked" and status != "LeanProofChecked":
        errors.append("root: claim_class LeanKernelChecked requires status LeanProofChecked")
    cert = data.get("certificate")
    if isinstance(cert, dict):
        errors.extend(_validate_pfcore_certificate(cert))
    return errors


def iter_pf_core_example_dirs(kind: str) -> list[Path]:
    root = repo_root() / "examples" / f"pf-core-{kind}"
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def load_pf_core_fixture_manifest(case_dir: Path) -> dict[str, Any]:
    manifest_path = case_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValidationError(f"Missing manifest.json in {case_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValidationError(f"manifest.json root must be an object in {case_dir}")
    return manifest


def check_pf_core_valid_fixtures() -> None:
    from pcs_core.pf_core_replay import replay_trace
    from pcs_core.validate_semantics import validate_file

    for case_dir in iter_pf_core_example_dirs("valid"):
        manifest = None
        manifest_path = case_dir / "manifest.json"
        if manifest_path.is_file():
            manifest = load_pf_core_fixture_manifest(case_dir)
        for path in sorted(case_dir.glob("*.json")):
            if path.name == "manifest.json":
                continue
            if path.name == "tool_use_trace.json" and (case_dir / "pfcore_trace.json").is_file():
                continue
            validate_file(path)
        if manifest and manifest.get("replay_required"):
            trace_path = case_dir / str(manifest.get("trace_file") or "trace.json")
            if trace_path.is_file():
                result = replay_trace(trace_path)
                if not result.match:
                    raise ValidationError(f"Replay failed for {case_dir}: {result.diffs!r}")


def check_pf_core_invalid_fixtures() -> None:
    from pcs_core.pf_core_contract import validate_trace_contracts
    from pcs_core.pf_core_runtime import (
        DroppedDeniedEvent,
        HandoffAuthorityExpansion,
        MissingPrincipal,
        UnknownCapability,
        UnknownEffect,
        compile_runtime_observation_to_event,
        compile_tool_use_trace_to_pfcore_trace,
        validate_denied_events_preserved,
        validate_handoff_authority,
        validate_pfcore_trace_hash_chain,
    )

    for case_dir in iter_pf_core_example_dirs("invalid"):
        manifest = load_pf_core_fixture_manifest(case_dir)
        expected_error = str(manifest["expected_error"])
        must_fail_at = str(manifest["must_fail_at"])

        if must_fail_at == "runtime_to_pfcore_event":
            observation = json.loads((case_dir / "observation.json").read_text(encoding="utf-8"))
            try:
                compile_runtime_observation_to_event(observation)
            except (UnknownCapability, UnknownEffect, MissingPrincipal) as exc:
                if exc.code != expected_error:
                    raise ValidationError(
                        f"{case_dir}: expected {expected_error!r}, got {exc.code!r}"
                    ) from exc
            except ValidationError as exc:
                combined = " ".join(exc.errors or []) + " " + str(exc)
                if expected_error == "UnknownEffect" and (
                    expected_error in combined
                    or "effect_kind" in combined
                    or "is not one of" in combined
                ):
                    pass
                elif expected_error == "UnknownCapability" and (
                    expected_error in combined or "capability_id" in combined
                ):
                    pass
                elif expected_error not in combined:
                    raise ValidationError(
                        f"{case_dir}: expected {expected_error!r}, got schema/validation {combined!r}"
                    ) from exc
            else:
                raise ValidationError(f"Expected {case_dir} to fail at {must_fail_at}")
            continue

        if must_fail_at == "validate_pfcore_trace_hash_chain":
            trace = json.loads((case_dir / "trace.json").read_text(encoding="utf-8"))
            errors = validate_pfcore_trace_hash_chain(trace)
            if not any(expected_error in err for err in errors):
                raise ValidationError(
                    f"Expected {case_dir} to fail with {expected_error!r}, got {errors!r}"
                )
            continue

        if must_fail_at == "validate_denied_events_preserved":
            tool_use_trace = json.loads(
                (case_dir / "tool_use_trace.json").read_text(encoding="utf-8")
            )
            pfcore_trace = json.loads((case_dir / "pfcore_trace.json").read_text(encoding="utf-8"))
            try:
                validate_denied_events_preserved(tool_use_trace, pfcore_trace)
            except DroppedDeniedEvent as exc:
                if exc.code != expected_error:
                    raise ValidationError(
                        f"{case_dir}: expected {expected_error!r}, got {exc.code!r}"
                    ) from exc
            else:
                raise ValidationError(f"Expected {case_dir} to fail at {must_fail_at}")
            continue

        if must_fail_at == "validate_denied_observations_preserved":
            from pcs_core.pf_core_runtime import validate_denied_observations_preserved

            observations = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in sorted(case_dir.glob("observation*.json"))
            ]
            pfcore_trace = json.loads((case_dir / "pfcore_trace.json").read_text(encoding="utf-8"))
            events = pfcore_trace.get("events")
            if not isinstance(events, list):
                raise ValidationError(f"{case_dir}: pfcore_trace.json missing events array")
            try:
                validate_denied_observations_preserved(observations, events)
            except DroppedDeniedEvent as exc:
                if exc.code != expected_error:
                    raise ValidationError(
                        f"{case_dir}: expected {expected_error!r}, got {exc.code!r}"
                    ) from exc
            else:
                raise ValidationError(f"Expected {case_dir} to fail at {must_fail_at}")
            continue

        if must_fail_at == "compile_runtime_observations_to_pfcore_trace":
            from pcs_core.pf_core_runtime import compile_runtime_observations_to_pfcore_trace

            observations = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in sorted(case_dir.glob("observation*.json"))
            ]
            try:
                compile_runtime_observations_to_pfcore_trace(observations)
            except DroppedDeniedEvent as exc:
                if exc.code != expected_error:
                    raise ValidationError(
                        f"{case_dir}: expected {expected_error!r}, got {exc.code!r}"
                    ) from exc
            else:
                raise ValidationError(f"Expected {case_dir} to fail at {must_fail_at}")
            continue

        if must_fail_at == "validate_semantics":
            from pcs_core.validate_semantics import validate_semantics

            artifact_file = str(manifest.get("artifact_file") or "trace.json")
            artifact_type = str(manifest.get("artifact_type") or "")
            data = json.loads((case_dir / artifact_file).read_text(encoding="utf-8"))
            detected = artifact_type or detect_artifact_type(data)
            if not detected:
                raise ValidationError(f"{case_dir}: could not detect artifact type")
            semantic_errors = validate_semantics(data, detected)
            if not any(expected_error in err for err in semantic_errors):
                raise ValidationError(
                    f"Expected {case_dir} to fail with {expected_error!r}, got {semantic_errors!r}"
                )
            continue

        if must_fail_at == "check_pfcore_trace_lean_semantics":
            from pcs_core.lean_check import check_pfcore_trace_lean_semantics

            trace = json.loads((case_dir / "trace.json").read_text(encoding="utf-8"))
            issues = check_pfcore_trace_lean_semantics(trace)
            if not any(issue.code == expected_error for issue in issues):
                raise ValidationError(
                    f"Expected {case_dir} to fail with {expected_error!r}, got "
                    f"{[issue.code for issue in issues]!r}"
                )
            continue

        if must_fail_at == "validate_handoff_authority":
            handoff = json.loads((case_dir / "handoff.json").read_text(encoding="utf-8"))
            try:
                validate_handoff_authority(handoff)
            except HandoffAuthorityExpansion as exc:
                if exc.code != expected_error:
                    raise ValidationError(
                        f"{case_dir}: expected {expected_error!r}, got {exc.code!r}"
                    ) from exc
            else:
                raise ValidationError(f"Expected {case_dir} to fail at {must_fail_at}")
            continue

        if must_fail_at == "compile_tool_use_trace_to_pfcore_trace":
            tool_use_trace = json.loads(
                (case_dir / "tool_use_trace.json").read_text(encoding="utf-8")
            )
            try:
                compile_tool_use_trace_to_pfcore_trace(tool_use_trace)
            except HandoffAuthorityExpansion as exc:
                if exc.code != expected_error:
                    raise ValidationError(
                        f"{case_dir}: expected {expected_error!r}, got {exc.code!r}"
                    ) from exc
            else:
                raise ValidationError(f"Expected {case_dir} to fail at {must_fail_at}")
            continue

        if must_fail_at == "validate_trace_contracts":
            trace = json.loads((case_dir / "trace.json").read_text(encoding="utf-8"))
            contracts_dir = case_dir / "contracts"
            contracts = {
                str(data["contract_id"]): data
                for data in (
                    json.loads(path.read_text(encoding="utf-8"))
                    for path in sorted(contracts_dir.glob("*.json"))
                )
            }
            issues = validate_trace_contracts(trace, contracts)
            if not any(issue.code == expected_error for issue in issues):
                raise ValidationError(
                    f"Expected {case_dir} to fail with {expected_error!r}, got "
                    f"{[issue.code for issue in issues]!r}"
                )
            continue

        if must_fail_at == "validate_tenant_isolation":
            from pcs_core.pf_core_runtime import validate_tenant_isolation

            trace = json.loads((case_dir / "trace.json").read_text(encoding="utf-8"))
            errors = validate_tenant_isolation(trace)
            if not any(expected_error in err for err in errors):
                raise ValidationError(
                    f"Expected {case_dir} to fail with {expected_error!r}, got {errors!r}"
                )
            continue

        raise ValidationError(f"Unknown must_fail_at {must_fail_at!r} in {case_dir}")
