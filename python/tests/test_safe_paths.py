"""Security tests for contained path resolution (POSIX + Windows forms)."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote

import pytest

from pcs_core.safe_paths import UnsafePathError, resolve_contained_file, strip_repo_generated_prefix


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / "ok.json").write_text("{}", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.lean").write_text("-- lean\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "ref",
    [
        "../../etc/passwd",
        "/etc/passwd",
        r"C:\Windows\system.ini",
        r"\\server\share\file",
        "//server/share/file",
        r"sub\..\..\etc\passwd",
        "sub/../../etc/passwd",
        "",
        "a\x00b.json",
        "x" * 5000,
    ],
)
def test_resolve_contained_file_rejects_traversal_and_absolutes(root: Path, ref: str) -> None:
    with pytest.raises(UnsafePathError):
        resolve_contained_file(root, ref)


def test_resolve_contained_file_accepts_relative(root: Path) -> None:
    path = resolve_contained_file(root, "ok.json", allowed_suffixes=frozenset({".json"}))
    assert path.is_file()
    nested = resolve_contained_file(root, "sub/nested.lean", allowed_suffixes=frozenset({".lean"}))
    assert nested.name == "nested.lean"


def test_resolve_contained_file_normalizes_backslashes(root: Path) -> None:
    path = resolve_contained_file(root, r"sub\nested.lean", allowed_suffixes=frozenset({".lean"}))
    assert path.is_file()


def test_url_encoded_traversal_rejected_when_decoded(root: Path) -> None:
    encoded = "..%2F..%2Fetc%2Fpasswd"
    decoded = unquote(encoded)
    with pytest.raises(UnsafePathError):
        resolve_contained_file(root, decoded)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_symlink_escape_rejected(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = root / "escape.json"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation failed: {exc}")
    with pytest.raises(UnsafePathError):
        resolve_contained_file(root, "escape.json", allowed_suffixes=frozenset({".json"}))


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_nested_symlink_rejected(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    target = outside / "secret.json"
    target.write_text("{}", encoding="utf-8")
    mid = root / "mid"
    try:
        mid.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation failed: {exc}")
    if not mid.is_symlink():
        pytest.skip("platform did not create a detectable directory symlink")
    with pytest.raises(UnsafePathError):
        resolve_contained_file(root, "mid/secret.json", allowed_suffixes=frozenset({".json"}))


def test_suffix_enforcement(root: Path) -> None:
    with pytest.raises(UnsafePathError):
        resolve_contained_file(root, "ok.json", allowed_suffixes=frozenset({".lean"}))


def test_strip_repo_generated_prefix() -> None:
    assert strip_repo_generated_prefix("lean/PFCore/Generated/Foo.lean") == "Foo.lean"
    assert strip_repo_generated_prefix(r"lean\PFCore\Generated\Foo.lean") == "Foo.lean"
    assert strip_repo_generated_prefix("Foo.lean") == "Foo.lean"


def test_proof_ref_outside_generated_rejected(tmp_path: Path) -> None:
    from pcs_core.lean_check import pfcore_generated_dir
    from pcs_core.pf_core_bundle import _resolve_proof_path

    generated = pfcore_generated_dir()
    generated.mkdir(parents=True, exist_ok=True)
    # Absolute / outside refs must fail.
    with pytest.raises(UnsafePathError):
        _resolve_proof_path({"proof_term_ref": str(tmp_path / "evil.lean")})
    with pytest.raises(UnsafePathError):
        _resolve_proof_path({"proof_term_ref": "lean/PFCore/Trace.lean"})


def test_bundle_validate_rejects_manifest_path_traversal(tmp_path: Path) -> None:
    from pcs_core.pf_core_bundle import validate_bundle

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(
        json_dumps(
            {
                "schema_version": "v0",
                "artifact_type": "PFCoreReleaseBundleManifest.v0",
                "trace_path": "../../etc/passwd",
                "certificate_path": "certificate.json",
                "trace_hash": "sha256:" + "a" * 64,
                "proof_term_hash": "sha256:" + "b" * 64,
                "kernel_manifest_path": "kernel_manifest.json",
                "pfcore_kernel_hash": "sha256:" + "c" * 64,
                "lean_environment_hash": "sha256:" + "d" * 64,
                "certificate_mode": "TraceSafeCertificate",
                "signature_or_digest": "sha256:" + "e" * 64,
            }
        ),
        encoding="utf-8",
    )
    result = validate_bundle(bundle)
    assert not result.ok
    # Phase 1: closed schema rejects parent-segment paths before filesystem resolve.
    assert any(
        issue.code in {"ManifestSchemaInvalid", "TracePathUnsafe"} for issue in result.issues
    )


def json_dumps(obj: dict) -> str:
    import json

    return json.dumps(obj, indent=2)


def test_fuzz_manifest_path_refs(root: Path) -> None:
    """Lightweight fuzz over manifest-like path refs (no hypothesis dependency)."""
    payloads = [
        "../x",
        "..\\x",
        "/x",
        "C:/x",
        "\\\\x\\y",
        "\x00",
        "." * 100,
        "a/./b",
        "sub/nested.lean",
        "ok.json",
    ]
    for payload in payloads:
        try:
            resolve_contained_file(root, payload)
        except UnsafePathError:
            continue
        # Only relative files under root may succeed.
        assert Path(payload.replace("\\", "/")).name in {"ok.json", "nested.lean"}
