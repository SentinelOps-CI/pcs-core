"""Tests for the authoritative PCS/PF-Core asset resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from pcs_core import asset_resolver as ar
from pcs_core.paths import package_dir, repo_root


def test_distribution_root_is_checkout_or_package() -> None:
    root = ar.distribution_root()
    assert root is not None
    assert root in {repo_root().resolve(), package_dir().resolve()} or root.is_dir()


def test_lean_root_resolves_lakefile() -> None:
    lean = ar.lean_root()
    assert lean is not None
    assert (lean / "lakefile.lean").is_file()
    assert ar.require_lean_root() == lean


def test_kernel_and_generated_roots() -> None:
    pf = ar.pf_core_kernel_root()
    pcs = ar.pcs_kernel_root()
    assert pf.is_dir()
    assert pcs.is_dir()
    assert ar.pf_core_generated_root() == pf / "Generated"
    assert ar.pcs_generated_root() == pcs / "Generated"


def test_pins_and_catalog() -> None:
    pins = ar.pins_dir()
    assert pins is not None
    assert (pins / "elan.json").is_file()
    assert ar.pin_path("elan.json").is_file()
    assert ar.pin_path("python-base-image.json").is_file()
    catalog = ar.catalog_dir()
    assert catalog is not None
    assert (catalog / "pf_core.catalog.json").is_file()


def test_relative_to_distribution_stable_for_kernel_file() -> None:
    lean = ar.require_lean_root()
    sample = next((lean / "PFCore").glob("*.lean"))
    rel = ar.relative_to_distribution(sample)
    assert rel.replace("\\", "/").startswith("lean/PFCore/")
    assert not Path(rel).is_absolute()


def test_lean_root_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = tmp_path / "lean"
    fake.mkdir()
    (fake / "lakefile.lean").write_text("-- test\n", encoding="utf-8")
    monkeypatch.setenv(ar.ENV_LEAN_ROOT, str(fake))
    assert ar.lean_root() == fake.resolve()


def test_resolver_report_shape() -> None:
    report = ar.resolver_report()
    assert "lean_root" in report
    assert "pins_dir" in report
    assert "catalog_dir" in report
    assert report["lean_project_present"] is True
    assert report["schemas_available"] is True


def test_capabilities_surfaces_resolver_paths() -> None:
    from pcs_core.capabilities import detect_capabilities

    report = detect_capabilities()
    paths = report["paths"]
    assert "distribution_root" in paths
    assert "pins_dir" in paths
    assert paths["lean_dir"] is not None
