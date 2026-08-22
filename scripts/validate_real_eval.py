import argparse
import json
from pathlib import Path

from tenderlens.evaluation.real_dataset import (
    load_real_evaluation_manifest,
    validate_real_evaluation_files,
)

DEFAULT_MANIFEST = Path("evals/real/manifest.local.json")
DEFAULT_DOCUMENTS = Path("evals/real/documents")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the private real-document evaluation holdout."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--documents", type=Path, default=DEFAULT_DOCUMENTS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_real_evaluation_manifest(args.manifest)
    summary = validate_real_evaluation_files(manifest, args.documents)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
