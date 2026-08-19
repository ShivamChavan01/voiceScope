#!/usr/bin/env python3
"""
Run the VoiceScope harness benchmark on labeled test data and report accuracy.

Exit code 0 when the benchmark passes, 1 when it regresses below MIN_TRUTH_SCORE.

Usage:
    python scripts/run_benchmark.py [--min-truth 0.7] [--json benchmark_result.json]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.benchmark import HarnessBenchmark  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-truth", type=float, default=0.7)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    summary = HarnessBenchmark().run_benchmark()

    print("=" * 62)
    print("  VoiceScope Harness Benchmark")
    print("=" * 62)
    if summary.total_tests == 0:
        print("  No labeled test data found. Skipping.")
        return 0
    print(f"  Tests:                  {summary.total_tests}")
    print(f"  Avg truth score:        {summary.avg_truth_score:.4f}")
    print(f"  Sentiment accuracy:     {summary.sentiment_accuracy:.1%}")
    print(f"  Outcome accuracy:       {summary.outcome_accuracy:.1%}")
    print(f"  Hallucination accuracy: {summary.hallucination_accuracy:.1%}")
    print(f"  Escalation accuracy:    {summary.escalation_accuracy:.1%}")
    print(f"  Avg citation coverage:  {summary.avg_citation_coverage:.1%}")
    print(f"  Avg fact accuracy:      {summary.avg_fact_accuracy:.1%}")
    print(f"  Weakest layer:          {summary.weakest_layer}")
    print(f"  Strongest layer:        {summary.strongest_layer}")
    print("=" * 62)

    payload = summary.model_dump()
    if args.json:
        Path(args.json).write_text(json.dumps(payload, indent=2))

    if summary.avg_truth_score < args.min_truth:
        print(
            f"  FAIL: avg truth score {summary.avg_truth_score:.4f} "
            f"below threshold {args.min_truth}"
        )
        return 1

    print("  PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
