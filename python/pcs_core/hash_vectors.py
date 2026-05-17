"""Maintain frozen canonical hash test vectors."""

from __future__ import annotations

import argparse
import json

from pcs_core.hash import canonical_hash, canonical_json_bytes
from pcs_core.paths import examples_dir, hash_vectors_dir

VECTOR_SPECS: dict[str, str] = {
    "RuntimeReceipt.v0": "runtime_receipt.valid.json",
    "TraceCertificate.v0": "trace_certificate.valid.json",
    "ScienceClaimBundle.v0": "science_claim_bundle.certified.valid.json",
    "SignedScienceClaimBundle.v0": "signed_science_claim_bundle.valid.json",
}


def write_vectors(*, force: bool = False) -> None:
    root = hash_vectors_dir()
    examples = examples_dir()
    for name, example_name in VECTOR_SPECS.items():
        out_dir = root / name
        out_dir.mkdir(parents=True, exist_ok=True)
        example_path = examples / example_name
        data = json.loads(example_path.read_text(encoding="utf-8"))
        canonical = canonical_json_bytes(data).decode("utf-8")
        digest = canonical_hash(data)
        input_path = out_dir / "input.json"
        canonical_path = out_dir / "canonical.txt"
        digest_path = out_dir / "digest.txt"
        if force or not input_path.exists():
            input_path.write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        canonical_path.write_text(canonical + "\n", encoding="utf-8")
        digest_path.write_text(digest + "\n", encoding="utf-8")


def verify_vectors() -> list[str]:
    errors: list[str] = []
    root = hash_vectors_dir()
    for name in VECTOR_SPECS:
        vector_dir = root / name
        data = json.loads((vector_dir / "input.json").read_text(encoding="utf-8"))
        expected_canonical = (vector_dir / "canonical.txt").read_text(encoding="utf-8").strip()
        expected_digest = (vector_dir / "digest.txt").read_text(encoding="utf-8").strip()
        actual_canonical = canonical_json_bytes(data).decode("utf-8")
        actual_digest = canonical_hash(data)
        if actual_canonical != expected_canonical:
            errors.append(
                f"{name}: canonical JSON drift (run python -m pcs_core.hash_vectors --write)"
            )
        if actual_digest != expected_digest:
            errors.append(f"{name}: digest drift (expected {expected_digest}, got {actual_digest})")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="PCS hash test vectors")
    parser.add_argument("--write", action="store_true", help="Regenerate vector files")
    parser.add_argument("--verify", action="store_true", help="Verify vectors match algorithm")
    args = parser.parse_args()
    if args.write:
        write_vectors(force=True)
        print(f"Wrote hash vectors under {hash_vectors_dir()}")
        return
    if args.verify:
        drift = verify_vectors()
        if drift:
            for err in drift:
                print(err)
            raise SystemExit(1)
        print("OK hash vectors")
        return
    parser.print_help()


if __name__ == "__main__":
    main()
