import argparse
import json
from pathlib import Path

from tenderlens.evaluation.quality_gate import evaluate_gate

DEFAULT_REPORT = Path("evals/real/reports/current.json")
DEFAULT_GATE = Path("evals/real/quality_gate.json")
DEFAULT_DECISION = Path("evals/real/reports/promotion-decision.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the real holdout quality gate.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_DECISION)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    gate = json.loads(args.gate.read_text(encoding="utf-8"))
    decision = evaluate_gate(report, gate)
    rendered = json.dumps(decision, ensure_ascii=False, indent=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if decision["enable_reranker_by_default"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
