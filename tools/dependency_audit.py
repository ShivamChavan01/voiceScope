"""Evaluate the raw audit with a short-lived exception for embedded Chroma only."""

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone

EXPIRES = date(2026, 11, 7)
CHROMA_IDS = frozenset({'PYSEC-2026-311', 'PYSEC-2026-3813', 'PYSEC-2026-3814', 'PYSEC-2026-3815'})


def assess(report: dict, today: date) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    exceptions: list[str] = []
    dependencies = report.get('dependencies') if isinstance(report, dict) else None
    if not isinstance(dependencies, list) or not dependencies:
        return ['Audit returned no dependency inventory'], []
    for dependency in dependencies:
        if not isinstance(dependency, dict) or not isinstance(dependency.get('name'), str):
            return ['Invalid dependency inventory'], []
        if dependency.get('skip_reason'):
            failures.append(f"Unscanned dependency: {dependency['name']}")
            continue
        vulnerabilities = dependency.get('vulns')
        if not isinstance(vulnerabilities, list) or not isinstance(dependency.get('version'), str):
            return ['Invalid dependency scan result'], []
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict) or not isinstance(vulnerability.get('id'), str) or not isinstance(dependency.get('version'), str):
                return ['Invalid vulnerability record'], []
            if not isinstance(vulnerability.get('fix_versions'), list):
                return ['Invalid vulnerability fix metadata'], []
            identity = f"{dependency['name']} {dependency['version']} {vulnerability['id']}"
            if (dependency['name'] == 'chromadb' and dependency['version'] == '1.5.9'
                    and vulnerability['id'] in CHROMA_IDS and today < EXPIRES
                    and not vulnerability.get('fix_versions')):
                exceptions.append(identity)
            else:
                failures.append(identity)
    return failures, sorted(set(exceptions))


def main(inventory: str | None = None) -> int:
    command = [sys.executable, '-m', 'pip_audit', '-r', inventory or 'requirements.txt',
               '--format', 'json', '--progress-spinner', 'off', '--timeout', '20']
    if inventory is not None:
        command.extend(['--no-deps', '--disable-pip'])
    try:
        result = subprocess.run(command,
                                capture_output=True, text=True, timeout=600)
    except (subprocess.TimeoutExpired, OSError):
        print('Audit tool unavailable or timed out', file=sys.stderr)
        return 1
    try:
        report = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        print('Audit failed to produce a valid report', file=sys.stderr)
        return 1
    if result.returncode not in (0, 1):
        print('Audit tool failed', file=sys.stderr)
        return 1
    failures, exceptions = assess(report, datetime.now(timezone.utc).date())
    for item in exceptions:
        print(f'REVIEWED EXCEPTION until {EXPIRES}: {item}; embedded-only, see docs/chroma-advisory-assessment.md')
    for item in failures:
        print(f'BLOCKED: {item}')
    return int(bool(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', help='Audit a complete, exactly pinned installed-package inventory without dependency resolution')
    raise SystemExit(main(parser.parse_args().inventory))
