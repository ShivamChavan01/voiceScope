#!/usr/bin/env python3
"""Measure policy detector predictions without passing expected labels to the detector."""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.reliability_benchmark import run_reliability_benchmark  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--dataset', type=Path)
    parser.add_argument('--min-case-accuracy', type=float, default=1.0)
    args = parser.parse_args()
    if not math.isfinite(args.min_case_accuracy) or not 0 <= args.min_case_accuracy <= 1:
        parser.error('--min-case-accuracy must be a finite number between 0 and 1')
    try:
        result = run_reliability_benchmark(args.dataset)
        if args.json:
            args.json.write_text(json.dumps(result.model_dump(mode='json'), indent=2) + '\n')
    except (OSError, ValueError) as exc:
        print(f'Policy benchmark unavailable: {exc}', file=sys.stderr)
        return 1
    print(f'Policy detector: {result.passed_cases}/{result.total_cases} exact case matches')
    print(f'Supported patterns: {result.supported_passed}/{result.supported_cases}')
    print(f'Challenge paraphrases: {result.challenge_passed}/{result.challenge_cases}')
    print(f'Finding counts: TP={result.metrics.true_positives}, FP={result.metrics.false_positives}, FN={result.metrics.false_negatives}')
    for case in result.results:
        if not case.passed:
            print(f'MISMATCH: {case.id} ({case.scope})')
    print('Synthetic regression set; not a held-out production accuracy estimate.')
    passed = result.exact_case_accuracy >= args.min_case_accuracy
    print('PASS' if passed else 'FAIL: exact case agreement below configured threshold')
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
