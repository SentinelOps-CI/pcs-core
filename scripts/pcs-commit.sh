#!/usr/bin/env bash
# Commit with hooks disabled so Cursor cannot append Co-authored-by trailers.
# Usage: scripts/pcs-commit.sh -m "Your message"
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EMPTY_HOOKS="${ROOT}/.git/empty-hooks"
mkdir -p "${EMPTY_HOOKS}"

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 -m \"message\" | -F message.txt" >&2
  exit 1
fi

git -C "${ROOT}" -c core.hooksPath=.git/empty-hooks commit "$@"
git -C "${ROOT}" log -1 --format=%B
