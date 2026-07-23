"""Registered declarative release-profile specs for PCS domains.

Compatibility wrappers in ``release_chain``, ``tool_use_release_chain``, and
``computation_release_chain`` delegate to the engine with these specs. Domain
validator bodies remain attached via ``legacy_validator`` until structural
parity is fully proven against the declarative pipeline alone.
"""

from __future__ import annotations

from pathlib import Path

from pcs_core.computation_release_chain import (
    COMPUTATION_COMMIT_KEYS,
    COMPUTATION_HANDOFF_FILES,
    COMPUTATION_MANIFEST_ARTIFACTS,
    COMPUTATION_RELEASE_PCS_ARTIFACTS,
)
from pcs_core.release_chain_profiles import (
    COMPUTATION_WORKFLOW_PROFILE_ID,
    LABTRUST_WORKFLOW_PROFILE_ID,
    TOOL_USE_WORKFLOW_PROFILE_ID,
)
from pcs_core.release_fixtures import (
    COMMIT_KEYS,
    MANIFEST_ARTIFACTS,
    RELEASE_PCS_ARTIFACTS,
)
from pcs_core.release_profile_engine import ReleaseProfileSpec, register_release_profile
from pcs_core.tool_use_release_chain import (
    TOOL_USE_COMMIT_KEYS,
    TOOL_USE_HANDOFF_FILES,
    TOOL_USE_MANIFEST_ARTIFACTS,
    TOOL_USE_RELEASE_PCS_ARTIFACTS,
)

LABTRUST_HANDOFF_FILES = (
    "handoff_to_certifyedge.json",
    "handoff_to_pf.json",
    "handoff_manifest.runtime_to_certificate.v0.json",
    "handoff_manifest.certificate_to_bundle.v0.json",
    "handoff_manifest.bundle_to_verifier.v0.json",
    "handoff_manifest.signed_bundle_to_memory.v0.json",
)


def _labtrust_legacy(directory: Path):
    from pcs_core.release_chain import _validate_labtrust_release_chain_impl

    return _validate_labtrust_release_chain_impl(directory)


def _tool_use_legacy(directory: Path):
    from pcs_core.tool_use_release_chain import _validate_tool_use_release_chain_impl

    return _validate_tool_use_release_chain_impl(directory)


def _computation_legacy(directory: Path):
    from pcs_core.computation_release_chain import _validate_computation_release_chain_impl

    return _validate_computation_release_chain_impl(directory)


LABTRUST_RELEASE_PROFILE = register_release_profile(
    ReleaseProfileSpec(
        workflow_profile_id=LABTRUST_WORKFLOW_PROFILE_ID,
        manifest_artifacts=MANIFEST_ARTIFACTS,
        release_pcs_artifacts=RELEASE_PCS_ARTIFACTS,
        handoff_files=LABTRUST_HANDOFF_FILES,
        commit_keys=COMMIT_KEYS,
        enforce_manifest_workflow_id=False,
        legacy_validator=_labtrust_legacy,
    ),
)

TOOL_USE_RELEASE_PROFILE = register_release_profile(
    ReleaseProfileSpec(
        workflow_profile_id=TOOL_USE_WORKFLOW_PROFILE_ID,
        manifest_artifacts=TOOL_USE_MANIFEST_ARTIFACTS,
        release_pcs_artifacts=TOOL_USE_RELEASE_PCS_ARTIFACTS,
        handoff_files=TOOL_USE_HANDOFF_FILES,
        commit_keys=TOOL_USE_COMMIT_KEYS,
        legacy_validator=_tool_use_legacy,
    ),
)

COMPUTATION_RELEASE_PROFILE = register_release_profile(
    ReleaseProfileSpec(
        workflow_profile_id=COMPUTATION_WORKFLOW_PROFILE_ID,
        manifest_artifacts=COMPUTATION_MANIFEST_ARTIFACTS,
        release_pcs_artifacts=COMPUTATION_RELEASE_PCS_ARTIFACTS,
        handoff_files=COMPUTATION_HANDOFF_FILES,
        commit_keys=COMPUTATION_COMMIT_KEYS,
        legacy_validator=_computation_legacy,
    ),
)
