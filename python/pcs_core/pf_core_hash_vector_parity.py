"""Compare PCS hash vectors with provability-fabric-core adapter fixtures (native parity)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from pcs_core.paths import repo_root

DEFAULT_PF_CORE_TAG = "pf-core-v0.6.0"
DEFAULT_PF_CORE_REPO = "https://github.com/SentinelOps-CI/provability-fabric-core.git"
UPSTREAM_REL = Path("adapters/pcs/tests/fixtures/hash_vectors")


def hash_vectors_dir(local: Path | None = None) -> Path:
    return local or (repo_root() / "python" / "tests" / "hash_vectors")


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _clone_upstream(
    *,
    pf_core_tag: str,
    pf_core_repo: str,
    work_dir: Path,
) -> Path:
    dest = work_dir / "provability-fabric-core"
    if dest.is_dir():
        shutil.rmtree(dest)
    proc = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            pf_core_tag,
            pf_core_repo,
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"git clone {pf_core_tag} failed: {detail}")
    upstream = dest / UPSTREAM_REL
    if not upstream.is_dir():
        raise RuntimeError(f"missing upstream hash vectors at {upstream}")
    return upstream


def compare_hash_vector_trees(local: Path, upstream: Path) -> list[str]:
    """Return drift messages; empty when every upstream vector matches locally."""
    errors: list[str] = []
    upstream_files = sorted(
        path
        for path in upstream.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    )
    for upstream_file in upstream_files:
        rel = upstream_file.relative_to(upstream)
        local_file = local / rel
        if not local_file.is_file():
            errors.append(f"missing local vector: {rel.as_posix()}")
            continue
        local_text = _normalize_text(local_file.read_text(encoding="utf-8"))
        upstream_text = _normalize_text(upstream_file.read_text(encoding="utf-8"))
        if local_text != upstream_text:
            errors.append(
                f"hash vector drift: {rel.as_posix()} "
                f"(expected match with upstream provability-fabric-core fixtures)"
            )
    return errors


def verify_pf_core_hash_vectors(
    local: Path | None = None,
    *,
    pf_core_tag: str | None = None,
    pf_core_repo: str | None = None,
    upstream_dir: Path | None = None,
    work_dir: Path | None = None,
) -> list[str]:
    """
    Verify local PCS hash vectors match provability-fabric-core adapter fixtures.

    When ``upstream_dir`` is omitted, clones ``pf_core_tag`` into a temporary
    directory (or ``work_dir`` when provided).
    """
    local_root = hash_vectors_dir(local)
    tag = pf_core_tag or os.environ.get("PF_CORE_TAG", DEFAULT_PF_CORE_TAG)
    repo = pf_core_repo or os.environ.get("PF_CORE_REPO", DEFAULT_PF_CORE_REPO)

    cleanup: Path | None = None
    try:
        if upstream_dir is not None:
            upstream_root = upstream_dir
        else:
            base = work_dir or Path(tempfile.mkdtemp(prefix="pf-core-hash-vectors-"))
            cleanup = None if work_dir else base
            upstream_root = _clone_upstream(
                pf_core_tag=tag,
                pf_core_repo=repo,
                work_dir=base,
            )
        return compare_hash_vector_trees(local_root, upstream_root)
    finally:
        if cleanup is not None and cleanup.is_dir():
            shutil.rmtree(cleanup, ignore_errors=True)
