#!/usr/bin/env bash
# Validate Phase 2 pinning / distribution scaffolding without running the full suite.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

python3 - <<'PY'
import json
from pathlib import Path

pins = Path("pins")
for name in ("elan.json", "certifyedge.json", "github-actions.json", "python-base-image.json"):
    path = pins / name
    assert path.is_file(), path
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), name

base = json.loads((pins / "python-base-image.json").read_text(encoding="utf-8"))
assert base["index_digest"].startswith("sha256:")
assert base["dockerfile_from"].endswith(base["index_digest"])
df = Path("docker/verifier/Dockerfile").read_text(encoding="utf-8")
assert base["index_digest"] in df
assert "USER pcs" in df

elan = json.loads((pins / "elan.json").read_text(encoding="utf-8"))
assert len(elan["sha256"]) == 64
actions = json.loads((pins / "github-actions.json").read_text(encoding="utf-8"))["actions"]
for key, meta in actions.items():
    assert len(meta["sha"]) == 40, key

lock = Path("python/requirements.lock")
assert lock.is_file()
assert "jsonschema==" in lock.read_text(encoding="utf-8")
assert Path("rust/Cargo.lock").is_file()
assert Path("typescript/package-lock.json").is_file()
assert Path("docker/verifier/Dockerfile").is_file()
assert Path("SECURITY.md").is_file()
assert Path(".github/CODEOWNERS").is_file()
assert Path(".github/dependabot.yml").is_file()
assert Path(".github/workflows/codeql.yml").is_file()
assert Path(".github/workflows/release-provenance.yml").is_file()
assert Path("scripts/build-release-provenance.sh").is_file()
assert Path("scripts/verify-release-provenance.sh").is_file()
assert Path("scripts/finalize-provenance-attestation.sh").is_file()
assert Path("schemas/ReleaseProvenanceBinding.v0.schema.json").is_file()
print("OK phase2 scaffolding checks")
PY

# Ensure workflows pin actions by SHA (40-char hex after @)
python3 - <<'PY'
from pathlib import Path
import re
wf = Path(".github/workflows")
pat = re.compile(r"uses:\s+[^\s@]+@([0-9a-f]{40})\b")
tag_pat = re.compile(r"uses:\s+[^\s@]+@(v?[0-9][^\s#]*)")
for path in sorted(wf.glob("*.yml")):
    text = path.read_text(encoding="utf-8")
    for m in tag_pat.finditer(text):
        ref = m.group(1)
        # Allow only when the same line also has a SHA (commented form uses SHA as primary)
        line = text[text.rfind("\n", 0, m.start()) + 1 : text.find("\n", m.start())]
        if not re.search(r"@[0-9a-f]{40}\b", line):
            raise SystemExit(f"FAIL unpinned action in {path}: {line.strip()}")
    assert pat.search(text), f"no SHA-pinned actions in {path}"
print("OK workflow action SHA pins")
PY

bash scripts/generate-sbom.sh "${ROOT}/dist/sbom"
test -f "${ROOT}/dist/sbom/pcs-core.cdx.json"
echo "OK phase2 smoke"
