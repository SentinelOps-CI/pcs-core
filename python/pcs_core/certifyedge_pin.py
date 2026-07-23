"""CertifyEdge pin loading, trust grade, and provision-environment contract.

Production pin (`pins/certifyedge.json`) remains ``status=unpinned`` until an
immutable CertifyEdge OCI digest / signed binary / locked source commit is
published. Do not invent placeholder digests.

``dev_fixture`` provisions a deterministic local fixture for tests and
preview tooling only — never a production trust root.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from pcs_core.paths import repo_root

TrustGrade = Literal["pinned", "untrusted_development", "unpinned"]
ProvisionStrategy = Literal[
    "none",
    "oci_digest",
    "signed_binary",
    "source_commit_build",
    "dev_fixture",
]

DIGEST_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
COMMIT_RE = re.compile(r"^[a-f0-9]{40}$")
PLACEHOLDER_MARKERS = (
    "REPLACE_WITH",
    "REPLACE_ME",
    "example/certifyedge",
    "sha256:REPLACE",
)

# Deterministic fixture body used by scripts/certifyedge-dev-fixture.py and
# provision-certifyedge.sh (dev_fixture strategy). Digest is content-addressed.
DEV_FIXTURE_MARKER = b"PCS_CERTIFYEDGE_DEV_FIXTURE_V1\n"
PROVISION_ENV_NAME = "provision.env"
DEFAULT_INSTALL_DIR_REL = Path(".tools") / "certifyedge"


@dataclass(frozen=True)
class CertifyEdgePin:
    status: str
    version: str
    provision_strategy: str
    image: str
    image_digest: str
    binary_url: str
    binary_sha256: str
    source_repo: str
    source_commit: str
    pin_identity: str
    raw: Mapping[str, Any]

    @property
    def is_pinned(self) -> bool:
        return self.status == "pinned"

    @property
    def expected_binary_digest(self) -> str | None:
        if self.provision_strategy in {"signed_binary", "dev_fixture"}:
            digest = self.binary_sha256.strip()
            if DIGEST_RE.match(digest):
                return digest
            if re.fullmatch(r"[a-f0-9]{64}", digest):
                return f"sha256:{digest}"
        if self.provision_strategy == "oci_digest" and DIGEST_RE.match(self.image_digest):
            return self.image_digest
        return None


@dataclass(frozen=True)
class ProvisionEnvironment:
    executable_path: str
    binary_digest: str
    version: str
    pin_identity: str
    provision_strategy: str
    trust_grade: TrustGrade

    def to_env_lines(self) -> list[str]:
        return [
            f"PCS_CERTIFYEDGE_EXECUTABLE={self.executable_path}",
            f"PCS_CERTIFYEDGE_BINARY_DIGEST={self.binary_digest}",
            f"PCS_CERTIFYEDGE_VERSION={self.version}",
            f"PCS_CERTIFYEDGE_PIN_IDENTITY={self.pin_identity}",
            f"PCS_CERTIFYEDGE_PROVISION_STRATEGY={self.provision_strategy}",
            f"PCS_CERTIFYEDGE_TRUST_GRADE={self.trust_grade}",
            # Compatibility alias consumed by existing workflows / CLI.
            f"PF_CORE_CERTIFYEDGE_CLI={self.executable_path}",
        ]

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self.to_env_lines()) + "\n", encoding="utf-8")
        return path


def _is_placeholder(value: str) -> bool:
    if not value or not value.strip():
        return True
    upper = value.upper()
    return any(marker.upper() in upper for marker in PLACEHOLDER_MARKERS)


def file_sha256_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def dev_fixture_digest() -> str:
    return f"sha256:{hashlib.sha256(DEV_FIXTURE_MARKER).hexdigest()}"


def pin_identity_from(pin: Mapping[str, Any]) -> str:
    status = str(pin.get("status") or "unknown")
    strategy = str(pin.get("provision_strategy") or "none")
    if strategy == "oci_digest":
        digest = str(pin.get("image_digest") or "")
        image = str(pin.get("image") or "certifyedge")
        return f"oci:{image}@{digest}" if digest else f"oci:{image}:unpinned"
    if strategy == "signed_binary":
        digest = str(pin.get("binary_sha256") or "")
        return f"binary:{digest}" if digest else "binary:unpinned"
    if strategy == "source_commit_build":
        commit = str(pin.get("source_commit") or "")
        repo = str(pin.get("source_repo") or "")
        return f"source:{repo}@{commit}" if commit else "source:unpinned"
    if strategy == "dev_fixture":
        digest = str(pin.get("binary_sha256") or dev_fixture_digest())
        return f"dev_fixture:{digest}"
    return f"{status}:{strategy}"


def load_certifyedge_pin(path: Path | None = None) -> CertifyEdgePin:
    pin_path = path or (repo_root() / "pins" / "certifyedge.json")
    data = json.loads(pin_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("certifyedge pin root must be a JSON object")
    return CertifyEdgePin(
        status=str(data.get("status") or "").strip().lower(),
        version=str(data.get("version") or "").strip(),
        provision_strategy=str(data.get("provision_strategy") or "none").strip().lower(),
        image=str(data.get("image") or ""),
        image_digest=str(data.get("image_digest") or ""),
        binary_url=str(data.get("binary_url") or ""),
        binary_sha256=str(data.get("binary_sha256") or ""),
        source_repo=str(data.get("source_repo") or ""),
        source_commit=str(data.get("source_commit") or ""),
        pin_identity=pin_identity_from(data),
        raw=data,
    )


def pin_is_production_ready(pin: CertifyEdgePin | Mapping[str, Any]) -> tuple[bool, list[str]]:
    """Return whether the pin can provision an immutable production CertifyEdge."""
    if isinstance(pin, CertifyEdgePin):
        status = pin.status
        strategy = pin.provision_strategy
        image = pin.image
        image_digest = pin.image_digest
        binary_url = pin.binary_url
        binary_sha256 = pin.binary_sha256
        source_repo = pin.source_repo
        source_commit = pin.source_commit
    else:
        status = str(pin.get("status") or "").strip().lower()
        strategy = str(pin.get("provision_strategy") or "").strip().lower()
        image = str(pin.get("image") or "")
        image_digest = str(pin.get("image_digest") or "")
        binary_url = str(pin.get("binary_url") or "")
        binary_sha256 = str(pin.get("binary_sha256") or "")
        source_repo = str(pin.get("source_repo") or "")
        source_commit = str(pin.get("source_commit") or "")

    errors: list[str] = []
    if status != "pinned":
        errors.append(f"status is {status!r}; need 'pinned' for release provisioning")
    if strategy in {"", "none"}:
        errors.append("provision_strategy is unset (none)")
        return False, errors

    if strategy == "dev_fixture":
        errors.append(
            "provision_strategy=dev_fixture is test/preview only; "
            "not production-ready (do not use for stable release trust)"
        )
        return False, errors

    if strategy == "oci_digest":
        if _is_placeholder(image):
            errors.append("image is empty or placeholder")
        if not DIGEST_RE.match(image_digest) or _is_placeholder(image_digest):
            errors.append("image_digest must be sha256:<64 hex> (no placeholders)")
    elif strategy == "signed_binary":
        if _is_placeholder(binary_url):
            errors.append("binary_url is empty or placeholder")
        if not DIGEST_RE.match(binary_sha256) and not re.fullmatch(r"[a-f0-9]{64}", binary_sha256):
            errors.append("binary_sha256 must be sha256:<64 hex> or bare 64-hex digest")
        if _is_placeholder(binary_sha256):
            errors.append("binary_sha256 is placeholder")
    elif strategy == "source_commit_build":
        if _is_placeholder(source_repo):
            errors.append("source_repo is empty or placeholder")
        if not COMMIT_RE.match(source_commit):
            errors.append("source_commit must be a full 40-char git SHA")
    else:
        errors.append(
            f"unknown provision_strategy {strategy!r}; "
            "expected oci_digest | signed_binary | source_commit_build"
        )
    return not errors, errors


def pin_allows_dev_fixture(pin: CertifyEdgePin | Mapping[str, Any]) -> tuple[bool, list[str]]:
    """Validate a test/dev fixture pin (preview/dev modes only)."""
    if isinstance(pin, CertifyEdgePin):
        status = pin.status
        strategy = pin.provision_strategy
        binary_sha256 = pin.binary_sha256
    else:
        status = str(pin.get("status") or "").strip().lower()
        strategy = str(pin.get("provision_strategy") or "").strip().lower()
        binary_sha256 = str(pin.get("binary_sha256") or "")

    errors: list[str] = []
    if strategy != "dev_fixture":
        errors.append(f"expected provision_strategy=dev_fixture, got {strategy!r}")
        return False, errors
    if status not in {"pinned", "dev_fixture"}:
        # Allow status=pinned for machine-readable fixture pins used only in tests.
        errors.append(f"dev_fixture pin status must be pinned or dev_fixture, got {status!r}")
    expected = dev_fixture_digest()
    normalized = binary_sha256.strip()
    if normalized and not DIGEST_RE.match(normalized) and re.fullmatch(r"[a-f0-9]{64}", normalized):
        normalized = f"sha256:{normalized}"
    if normalized and normalized != expected:
        errors.append(
            f"dev_fixture binary_sha256 mismatch: got {normalized!r}, expected {expected!r}"
        )
    return not errors, errors


def classify_checker_trust(
    *,
    executable: Path | None,
    pin: CertifyEdgePin | None = None,
    provision: ProvisionEnvironment | None = None,
) -> TrustGrade:
    """Classify a checker executable as pinned vs untrusted development-grade."""
    if provision is not None:
        return provision.trust_grade
    if pin is None:
        try:
            pin = load_certifyedge_pin()
        except (OSError, json.JSONDecodeError, ValueError):
            pin = None
    if pin is None or not pin.is_pinned:
        return "unpinned"
    ready, _ = pin_is_production_ready(pin)
    if not ready:
        if pin.provision_strategy == "dev_fixture":
            if executable is not None and executable.is_file():
                actual = file_sha256_digest(executable)
                expected = pin.expected_binary_digest or dev_fixture_digest()
                if actual == expected:
                    return "untrusted_development"
            return "untrusted_development"
        return "unpinned"
    if executable is None or not executable.is_file():
        return "unpinned"
    expected = pin.expected_binary_digest
    if expected is None:
        # source_commit_build: trust requires provision.env digest match later
        return "pinned"
    actual = file_sha256_digest(executable)
    if actual != expected:
        return "untrusted_development"
    return "pinned"


def parse_provision_env(path: Path) -> ProvisionEnvironment:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, _, value = text.partition("=")
        values[key.strip()] = value.strip()
    executable = (
        values.get("PCS_CERTIFYEDGE_EXECUTABLE") or values.get("PF_CORE_CERTIFYEDGE_CLI") or ""
    )
    digest = values.get("PCS_CERTIFYEDGE_BINARY_DIGEST") or ""
    version = values.get("PCS_CERTIFYEDGE_VERSION") or ""
    pin_identity = values.get("PCS_CERTIFYEDGE_PIN_IDENTITY") or ""
    strategy = values.get("PCS_CERTIFYEDGE_PROVISION_STRATEGY") or "none"
    grade_raw = values.get("PCS_CERTIFYEDGE_TRUST_GRADE") or "untrusted_development"
    if grade_raw not in {"pinned", "untrusted_development", "unpinned"}:
        grade_raw = "untrusted_development"
    if not executable:
        raise ValueError(f"provision env missing PCS_CERTIFYEDGE_EXECUTABLE: {path}")
    return ProvisionEnvironment(
        executable_path=executable,
        binary_digest=digest,
        version=version,
        pin_identity=pin_identity,
        provision_strategy=strategy,
        trust_grade=grade_raw,  # type: ignore[arg-type]
    )


def load_provision_environment(
    install_dir: Path | None = None,
) -> ProvisionEnvironment | None:
    """Load provision.env from install dir or ``PCS_CERTIFYEDGE_PROVISION_ENV``."""
    env_path = os.environ.get("PCS_CERTIFYEDGE_PROVISION_ENV", "").strip()
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return parse_provision_env(path)
    base = install_dir or (repo_root() / DEFAULT_INSTALL_DIR_REL)
    candidate = base / PROVISION_ENV_NAME
    if candidate.is_file():
        return parse_provision_env(candidate)
    return None


def build_provision_environment(
    *,
    executable: Path,
    pin: CertifyEdgePin,
    version: str | None = None,
) -> ProvisionEnvironment:
    digest = file_sha256_digest(executable)
    ready, _ = pin_is_production_ready(pin)
    if ready and (pin.expected_binary_digest is None or digest == pin.expected_binary_digest):
        grade: TrustGrade = "pinned"
    elif pin.provision_strategy == "dev_fixture":
        grade = "untrusted_development"
    elif pin.expected_binary_digest and digest == pin.expected_binary_digest:
        grade = "pinned"
    else:
        grade = "untrusted_development"
    return ProvisionEnvironment(
        executable_path=str(executable.resolve()),
        binary_digest=digest,
        version=version or pin.version or "unknown",
        pin_identity=pin.pin_identity,
        provision_strategy=pin.provision_strategy,
        trust_grade=grade,
    )


def write_dev_fixture_binary(dest: Path) -> str:
    """Write the deterministic CertifyEdge dev fixture and return its digest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # On Windows a .py fixture is used; on Unix we write a shebang script with
    # fixed body prefix so the digest remains stable when using the marker file.
    # Provisioning places the marker bytes as the executable content for digest
    # binding; the runnable wrapper is separate when needed.
    dest.write_bytes(DEV_FIXTURE_MARKER)
    return file_sha256_digest(dest)


def certifyedge_pin_record_for_bundle(pin: CertifyEdgePin | None = None) -> dict[str, Any]:
    """Machine-readable pin snapshot carried into release bundles."""
    loaded = pin or load_certifyedge_pin()
    ready, errors = pin_is_production_ready(loaded)
    return {
        "schema_version": "v0",
        "artifact_type": "CertifyEdgePinRecord.v0",
        "status": loaded.status,
        "version": loaded.version,
        "provision_strategy": loaded.provision_strategy,
        "pin_identity": loaded.pin_identity,
        "image": loaded.image,
        "image_digest": loaded.image_digest,
        "binary_sha256": loaded.binary_sha256,
        "source_repo": loaded.source_repo,
        "source_commit": loaded.source_commit,
        "production_ready": ready,
        "production_ready_errors": errors,
        "notes": list(loaded.raw.get("notes") or []),
    }


def validate_attestation_against_pin(
    attestation: Mapping[str, Any],
    *,
    pin: CertifyEdgePin | None = None,
    provision: ProvisionEnvironment | None = None,
    require_pinned: bool = False,
) -> list[str]:
    """Independent comparison of attestation fields vs trusted pin / provision env."""
    errors: list[str] = []
    loaded = pin
    if loaded is None:
        try:
            loaded = load_certifyedge_pin()
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            if require_pinned:
                return [f"CertifyEdgePinUnreadable: {exc}"]
            return []

    assert loaded is not None
    prov = provision or load_provision_environment()

    checker_digest = str(attestation.get("checker_binary_digest") or "")
    checker_version = str(attestation.get("checker_version") or "")
    issuer = str(attestation.get("issuer_identity") or "")
    property_id = str(attestation.get("property_id") or "")
    property_version = str(attestation.get("property_version") or "v0")
    trace_digest = str(attestation.get("trace_digest") or "")
    bundle_digest = str(attestation.get("release_bundle_digest") or "")

    if require_pinned:
        ready, pin_errors = pin_is_production_ready(loaded)
        if not ready:
            errors.append("CertifyEdgePinNotProductionReady: " + "; ".join(pin_errors))
            return errors

    expected_digest = None
    if prov is not None:
        expected_digest = prov.binary_digest
        if prov.version and checker_version and prov.version != checker_version:
            errors.append(
                f"CertifyEdgeVersionMismatch: attestation={checker_version!r} "
                f"provision={prov.version!r}"
            )
        if prov.pin_identity and prov.pin_identity not in issuer and issuer:
            # Issuer may be certifyedge-binary:<digest>; require digest or pin id match.
            if prov.binary_digest not in issuer and prov.pin_identity not in issuer:
                errors.append(
                    f"CertifyEdgeIssuerMismatch: issuer={issuer!r} "
                    f"pin_identity={prov.pin_identity!r}"
                )
        if prov.trust_grade == "untrusted_development" and require_pinned:
            errors.append(
                "CertifyEdgeUntrustedDevelopment: provision trust_grade="
                "untrusted_development (arbitrary/dev fixture checkers are not release-grade)"
            )
    else:
        expected_digest = loaded.expected_binary_digest

    if expected_digest and checker_digest and checker_digest != expected_digest:
        errors.append(
            f"CertifyEdgeBinaryDigestMismatch: attestation={checker_digest!r} "
            f"expected={expected_digest!r}"
        )

    if loaded.version and checker_version and loaded.version != checker_version and prov is None:
        errors.append(
            f"CertifyEdgeVersionMismatch: attestation={checker_version!r} pin={loaded.version!r}"
        )

    # Always require the attestation to carry the binding digests (independent of pin).
    if not DIGEST_RE.match(trace_digest):
        errors.append(f"CertifyEdgeTraceDigestInvalid: {trace_digest!r}")
    if not DIGEST_RE.match(bundle_digest):
        errors.append(f"CertifyEdgeBundleDigestInvalid: {bundle_digest!r}")
    if not property_id:
        errors.append("CertifyEdgePropertyMissing")
    else:
        # Policy digest is derived; recompute when helper available.
        from pcs_core.external_attestation import policy_digest_from_property

        expected_policy = policy_digest_from_property(property_id, property_version)
        recorded_policy = str(attestation.get("policy_digest") or "")
        if recorded_policy and recorded_policy != expected_policy:
            errors.append(
                f"CertifyEdgePolicyDigestMismatch: {recorded_policy!r} != {expected_policy!r}"
            )

    if (
        require_pinned
        and classify_checker_trust(executable=None, pin=loaded, provision=prov) != "pinned"
    ):
        errors.append("CertifyEdgeTrustGradeNotPinned: release requires pinned trust grade")

    return errors
