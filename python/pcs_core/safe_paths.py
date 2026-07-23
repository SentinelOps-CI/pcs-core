"""Containment-checked path resolution for untrusted refs."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath

# Conservative limit: reject absurdly long refs before filesystem work.
_MAX_REF_LENGTH = 4096

_CONTROL_OR_NUL_RE = re.compile(r"[\x00-\x1f\x7f]")

# Windows FILE_ATTRIBUTE_REPARSE_POINT — covers symlinks, junctions, and mounts.
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class UnsafePathError(ValueError):
    """Raised when a path ref fails containment or safety checks."""


def is_symlink_or_reparse_point(path: Path) -> bool:
    """True if ``path`` is a symlink or Windows reparse point (junction/mount)."""
    try:
        if path.is_symlink():
            return True
    except OSError:
        return True
    if os.name != "nt":
        return False
    try:
        st = path.lstat()
    except OSError:
        return True
    attrs = getattr(st, "st_file_attributes", None)
    if isinstance(attrs, int) and (attrs & _FILE_ATTRIBUTE_REPARSE_POINT):
        return True
    # Fallback: some Python builds omit st_file_attributes; treat S_IFLNK as link.
    return stat.S_ISLNK(st.st_mode)


def _is_windows_drive_or_unc(ref: str) -> bool:
    """Detect Windows drive paths and UNC shares in the raw ref string."""
    if re.match(r"^[A-Za-z]:[\\/]", ref):
        return True
    if ref.startswith("\\\\") or ref.startswith("//"):
        # UNC: \\server\share or //server/share
        return True
    pure = PureWindowsPath(ref.replace("/", "\\"))
    if pure.drive:
        return True
    # PureWindowsPath treats leading \\ as root; also catch //server/share forms.
    if pure.is_absolute() and (ref.startswith("\\") or ref.startswith("/")):
        # Absolute Windows-style without drive still rejected via POSIX absolute below
        # unless it is clearly a UNC form already handled.
        pass
    return bool(pure.anchor and pure.drive)


def _is_absolute_posix(ref: str) -> bool:
    normalized = ref.replace("\\", "/")
    return normalized.startswith("/")


def _has_parent_segment(ref: str) -> bool:
    normalized = ref.replace("\\", "/")
    return any(part == ".." for part in PurePosixPath(normalized).parts)


def _reject_symlink_components(path: Path) -> None:
    """Reject if any path component (including the final) is a symlink/reparse point."""
    # Walk from root toward the leaf so intermediate link escapes are caught.
    parts = path.parts
    if not parts:
        raise UnsafePathError("empty resolved path")
    # Absolute paths: rebuild incrementally from the anchor.
    current = Path(parts[0])
    if len(parts) == 1:
        if is_symlink_or_reparse_point(current):
            raise UnsafePathError(f"symlink or reparse point rejected: {current}")
        return
    for part in parts[1:]:
        current = current / part
        try:
            if is_symlink_or_reparse_point(current):
                raise UnsafePathError(f"symlink or reparse point rejected: {current}")
        except OSError as exc:
            raise UnsafePathError(f"cannot inspect path component {current}: {exc}") from exc


def resolve_contained_file(
    root: Path,
    ref: str,
    *,
    allowed_suffixes: frozenset[str] = frozenset(),
    reject_symlinks: bool = True,
) -> Path:
    """Resolve ``ref`` as a regular file strictly under ``root``.

    Rejects empty refs, absolute POSIX paths, Windows drive/UNC paths, ``..``
    segments, control characters / NUL, and excessively long refs. Normalizes
    backslashes to forward slashes before joining. Optionally rejects symlinks
    in every path component and enforces an allowlist of file suffixes.
    """
    if not isinstance(ref, str):
        raise UnsafePathError(f"path ref must be a string, got {type(ref).__name__}")
    if ref == "":
        raise UnsafePathError("empty path ref")
    if len(ref) > _MAX_REF_LENGTH:
        raise UnsafePathError(f"path ref exceeds maximum length {_MAX_REF_LENGTH}")
    if _CONTROL_OR_NUL_RE.search(ref):
        raise UnsafePathError("path ref contains control characters or NUL")
    if _is_windows_drive_or_unc(ref):
        raise UnsafePathError(f"absolute Windows / UNC path rejected: {ref!r}")
    if _is_absolute_posix(ref):
        raise UnsafePathError(f"absolute path rejected: {ref!r}")
    if _has_parent_segment(ref):
        raise UnsafePathError(f"parent-segment traversal rejected: {ref!r}")

    normalized = ref.replace("\\", "/")
    # Reject empty segments that would collapse oddly, and residual absolute forms.
    pure = PurePosixPath(normalized)
    if pure.is_absolute():
        raise UnsafePathError(f"absolute path rejected: {ref!r}")
    if any(part == ".." for part in pure.parts):
        raise UnsafePathError(f"parent-segment traversal rejected: {ref!r}")
    if any(part == "" for part in pure.parts):
        raise UnsafePathError(f"empty path segment rejected: {ref!r}")

    try:
        root_resolved = root.resolve(strict=True)
    except OSError as exc:
        raise UnsafePathError(f"root is not resolvable: {root}: {exc}") from exc
    if not root_resolved.is_dir():
        raise UnsafePathError(f"root is not a directory: {root_resolved}")

    # Walk lexically under root before resolve so intermediate symlinks/reparses are visible.
    lexical = root_resolved
    for part in pure.parts:
        lexical = lexical / part
        if reject_symlinks:
            try:
                if is_symlink_or_reparse_point(lexical):
                    raise UnsafePathError(f"symlink or reparse point rejected: {lexical}")
            except OSError as exc:
                raise UnsafePathError(f"cannot inspect path component {lexical}: {exc}") from exc

    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise UnsafePathError(f"path does not resolve under root: {ref!r}: {exc}") from exc

    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise UnsafePathError(f"path escapes containment root {root_resolved}: {ref!r}") from exc

    if reject_symlinks:
        _reject_symlink_components(resolved)

    if not resolved.is_file():
        raise UnsafePathError(f"path is not a regular file: {ref!r}")
    if is_symlink_or_reparse_point(resolved):
        # Belt-and-suspenders if is_file() followed a link on some platforms.
        raise UnsafePathError(f"symlink or reparse point rejected: {resolved}")

    if allowed_suffixes:
        suffix = resolved.suffix.lower()
        allowed = {s.lower() if s.startswith(".") else f".{s.lower()}" for s in allowed_suffixes}
        if suffix not in allowed:
            raise UnsafePathError(
                f"suffix {suffix!r} not in allowed set {sorted(allowed)!r} for {ref!r}"
            )

    return resolved


def strip_repo_generated_prefix(ref: str) -> str:
    """Strip a leading ``lean/PFCore/Generated/`` prefix from a proof ref."""
    normalized = ref.replace("\\", "/").lstrip("/")
    prefix = "lean/PFCore/Generated/"
    if normalized.startswith(prefix):
        return normalized[len(prefix) :]
    return normalized
