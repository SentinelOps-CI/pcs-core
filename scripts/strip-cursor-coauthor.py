#!/usr/bin/env python3
"""Remove Cursor co-author trailer lines from commit messages (filter-branch msg-filter)."""

from __future__ import annotations

import re
import sys

CURSOR_COAUTHOR = re.compile(
    r"^Co-authored-by:\s*Cursor\s*<cursoragent@cursor\.com>\s*$",
    re.IGNORECASE,
)

lines = sys.stdin.read().splitlines()
kept = [line for line in lines if not CURSOR_COAUTHOR.match(line)]
while kept and kept[-1] == "":
    kept.pop()
if kept:
    sys.stdout.write("\n".join(kept) + "\n")
