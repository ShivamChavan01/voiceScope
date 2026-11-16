"""Evaluate the complete raw dependency audit without vulnerability waivers."""

import argparse
import json
import subprocess
import sys

def assess(report: dict) -> list[str]:
    failures: list[str] = []
    dependencies = report.get('dependencies') if isinstance(report, dict) else None
    if not isinstance(dependencies, list) or not dependencies:
        return ['Audit returned no dependency inventory']
    for dependency in dependencies:
        if not isinstance(dependency, dict) or not isinstance(dependency.get('name'), str):
            return ['Invalid dependency inventory']
        if dependency.get('skip_reason'):
            failures.append(f"Unscanned dependency: {dependency['name']}")
            continue
        vulnerabilities = dependency.get('vulns')
        if not isinstance(vulnerabilities, list) or not isinstance(dependency.get('version'), str):
            return ['Invalid dependency scan result']
        if dependency['name'].lower().replace('_', '-') == 'chromadb':
            failures.append('Legacy Chroma must not be installed in the application runtime')
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict) or not isinstance(vulnerability.get('id'), str) or not isinstance(dependency.get('version'), str):
                return ['Invalid vulnerability record']
            if not isinstance(vulnerability.get('fix_versions'), list):
                return ['Invalid vulnerability fix metadata']
            identity = f"{dependency['name']} {dependency['version']} {vulnerability['id']}"
            failures.append(identity)
    return failures


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
    failures = assess(report)
    for item in failures:
        print(f'BLOCKED: {item}')
    return int(bool(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', help='Audit a complete, exactly pinned installed-package inventory without dependency resolution')
    raise SystemExit(main(parser.parse_args().inventory))
