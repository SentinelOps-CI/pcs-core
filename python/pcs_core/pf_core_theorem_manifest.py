"""PFCoreTheoremManifest.v0 — structured theorem IR shared by Lean codegen and binding."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pcs_core.hash import canonical_hash

_THEOREM_SIGNATURE_RE = re.compile(
    r"theorem\s+(\w+)(?:\s*\([^)]*\))*\s*:\s*(.+?)\s*:=",
    re.DOTALL,
)

THEOREM_CATEGORIES = frozenset(
    {
        "trace_safety",
        "event_safety",
        "trust_boundary",
        "resource_scope",
        "handoff_safety",
        "contract",
        "effect_frame",
        "transition",
        "compositional",
        "mode_aggregate",
        "mode_witness",
    }
)

CERTIFICATE_MODE_ROLES = frozenset(
    {
        "required",
        "supporting",
        "aggregate",
        "final_witness",
    }
)


def normalize_proposition(proposition: str) -> str:
    """Collapse Lean proposition whitespace to a stable normalized form."""
    return " ".join(str(proposition).split())


def proposition_hash(proposition: str) -> str:
    normalized = normalize_proposition(proposition)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def parse_theorem_signature(lean_theorem: str) -> tuple[str, str] | None:
    """Return (name, normalized_proposition) from a Lean theorem declaration."""
    match = _THEOREM_SIGNATURE_RE.search(lean_theorem)
    if match is None:
        return None
    return match.group(1), normalize_proposition(match.group(2))


@dataclass(frozen=True)
class TheoremSpec:
    """Structured intermediate representation for one generated theorem."""

    name: str
    normalized_proposition: str
    category: str
    generation_node: str
    evidence_artifact_ids: tuple[str, ...] = ()
    certificate_mode_role: str = "supporting"
    lean_text: str = ""

    def __post_init__(self) -> None:
        if self.category not in THEOREM_CATEGORIES:
            raise ValueError(f"invalid theorem category: {self.category!r}")
        if self.certificate_mode_role not in CERTIFICATE_MODE_ROLES:
            raise ValueError(f"invalid certificate_mode_role: {self.certificate_mode_role!r}")
        if not self.name or not self.name.isidentifier():
            raise ValueError(f"invalid theorem name: {self.name!r}")

    @property
    def proposition_hash(self) -> str:
        return proposition_hash(self.normalized_proposition)

    def to_entry(self) -> dict[str, Any]:
        return {
            "theorem_name": self.name,
            "normalized_proposition": normalize_proposition(self.normalized_proposition),
            "theorem_category": self.category,
            "generation_node": self.generation_node,
            "evidence_artifact_ids": list(self.evidence_artifact_ids),
            "certificate_mode_role": self.certificate_mode_role,
            "proposition_hash": self.proposition_hash,
        }

    def emit_lean(self) -> str:
        if self.lean_text.strip():
            return self.lean_text
        raise ValueError(f"theorem {self.name!r} has no lean_text to emit")


@dataclass
class TheoremBuildContext:
    """Collect theorem IR while emitting Lean; inventory is derived from the IR."""

    inventory: set[str] = field(default_factory=set)
    specs: list[TheoremSpec] = field(default_factory=list)

    def register_name(self, name: str) -> str:
        from pcs_core.pf_core_lean_codegen import register_theorem_name

        return register_theorem_name(self.inventory, name)

    def emit(
        self,
        lean_text: str,
        *,
        category: str,
        generation_node: str,
        evidence_artifact_ids: Sequence[str] | None = None,
        certificate_mode_role: str = "supporting",
    ) -> str:
        """Record a theorem from its Lean text into the shared IR and return the text."""
        parsed = parse_theorem_signature(lean_text)
        if parsed is None:
            raise ValueError(f"cannot parse theorem signature from: {lean_text[:120]!r}")
        name, prop = parsed
        self.register_name(name)
        self.specs.append(
            TheoremSpec(
                name=name,
                normalized_proposition=prop,
                category=category,
                generation_node=generation_node,
                evidence_artifact_ids=tuple(evidence_artifact_ids or ()),
                certificate_mode_role=certificate_mode_role,
                lean_text=lean_text,
            )
        )
        return lean_text

    def emit_spec(self, spec: TheoremSpec) -> str:
        self.register_name(spec.name)
        self.specs.append(spec)
        return spec.emit_lean()

    def theorem_names(self) -> frozenset[str]:
        return frozenset(self.inventory)


def build_theorem_manifest(
    *,
    specs: Sequence[TheoremSpec],
    generated_module_name: str,
    proof_file_hash: str,
    semantic_projection_hash: str,
    certificate_mode: str,
    final_witness_theorem: str,
    final_witness_proposition: str,
) -> dict[str, Any]:
    """Build PFCoreTheoremManifest.v0 from structured theorem IR."""
    if not specs:
        raise ValueError("theorem manifest requires ≥1 theorem spec")
    body: dict[str, Any] = {
        "schema_version": "v0",
        "artifact_type": "PFCoreTheoremManifest.v0",
        "generated_module_name": generated_module_name,
        "proof_file_hash": proof_file_hash,
        "semantic_projection_hash": semantic_projection_hash,
        "certificate_mode": certificate_mode,
        "final_witness_theorem": final_witness_theorem,
        "final_witness_proposition": normalize_proposition(final_witness_proposition),
        "theorems": [spec.to_entry() for spec in specs],
    }
    digest = compute_theorem_manifest_digest(body)
    body["theorem_manifest_digest"] = digest
    return body


def compute_theorem_manifest_digest(manifest: Mapping[str, Any]) -> str:
    """Canonical digest over the manifest excluding theorem_manifest_digest."""
    payload = {k: v for k, v in manifest.items() if k != "theorem_manifest_digest"}
    return canonical_hash(dict(payload))


def write_theorem_manifest(manifest: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(manifest), indent=2) + "\n", encoding="utf-8")
    return path


def load_theorem_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("theorem manifest root must be an object")
    return data


def theorem_names_from_manifest(manifest: Mapping[str, Any]) -> list[str]:
    theorems = manifest.get("theorems")
    if not isinstance(theorems, list):
        return []
    names: list[str] = []
    for entry in theorems:
        if isinstance(entry, Mapping):
            name = str(entry.get("theorem_name") or "")
            if name:
                names.append(name)
    return names


def propositions_by_name(manifest: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    theorems = manifest.get("theorems")
    if not isinstance(theorems, list):
        return out
    for entry in theorems:
        if not isinstance(entry, Mapping):
            continue
        name = str(entry.get("theorem_name") or "")
        prop = str(entry.get("normalized_proposition") or "")
        if name and prop:
            out[name] = normalize_proposition(prop)
    return out


def specs_match_inventory(specs: Iterable[TheoremSpec], inventory: Iterable[str]) -> bool:
    return frozenset(spec.name for spec in specs) == frozenset(str(n) for n in inventory)


def reconstruct_theorem_metadata_from_proof(proof_text: str) -> dict[str, str]:
    """Parse theorem name → normalized proposition from a generated Lean proof file.

    Expands ``SelectedCertificateModePredicate`` when the generated file defines
    that alias (final mode witness surface form).
    """
    alias_match = re.search(
        r"def\s+SelectedCertificateModePredicate\s*:\s*Prop\s*:=\s*(.+?)(?=\n\s*(?:theorem|def|end)\b)",
        proof_text,
        re.DOTALL,
    )
    alias_body = normalize_proposition(alias_match.group(1)) if alias_match else None

    reconstructed: dict[str, str] = {}
    for match in _THEOREM_SIGNATURE_RE.finditer(proof_text):
        name = match.group(1)
        prop = normalize_proposition(match.group(2))
        if prop == "SelectedCertificateModePredicate" and alias_body:
            prop = alias_body
        reconstructed[name] = prop
    return reconstructed
