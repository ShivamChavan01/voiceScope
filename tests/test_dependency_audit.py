import copy
from unittest.mock import patch
from types import SimpleNamespace
import subprocess
import json

import pytest

from tools.dependency_audit import assess, main


def report(identity='PYSEC-2026-3814', version='1.5.9', name='chromadb', fixes=None):
    return {'dependencies': [{'name': name, 'version': version, 'vulns': [{'id': identity, 'fix_versions': fixes or []}]}]}


@pytest.mark.parametrize('identity', ['PYSEC-2026-311', 'PYSEC-2026-3813', 'PYSEC-2026-3814', 'PYSEC-2026-3815'])
def test_previously_excepted_advisories_are_always_blocked(identity):
    assert any(identity in failure for failure in assess(report(identity)))


@pytest.mark.parametrize('data', [report(version='1.5.10'), report(name='other-package'),
    report(identity='NEW-UNREVIEWED'), report(fixes=['1.5.10']),
    {'dependencies': []}, {}])
def test_audit_blocks_all_vulnerabilities_and_invalid_reports(data):
    assert assess(data)


def test_legacy_dependency_is_rejected_even_if_scan_has_no_advisories():
    data = {'dependencies': [{'name': 'chromadb', 'version': '1.5.9', 'vulns': []}]}
    assert assess(data)


def test_unscanned_dependency_fails_and_input_is_not_mutated():
    data = {'dependencies': [{'name': 'unscanned', 'skip_reason': 'resolution failed'}]}
    original = copy.deepcopy(data)
    assert assess(data)
    assert data == original


def test_audit_tool_failure_is_not_a_clean_scan():
    with patch('tools.dependency_audit.subprocess.run', return_value=SimpleNamespace(stdout='not JSON', returncode=2)):
        assert main() == 1


@pytest.mark.parametrize('data', [None, {'dependencies': [None]},
    {'dependencies': [{'name': 'package', 'version': '1', 'vulns': [None]}]},
    {'dependencies': [{'name': 'package', 'version': '1'}]},
    {'dependencies': [{'name': 'package', 'version': '1', 'vulns': None}]},
    {'dependencies': [{'name': 'chromadb', 'version': '1.5.9', 'vulns': [{'id': 'PYSEC-2026-3814'}]}]},
])
def test_invalid_reports_fail_closed(data):
    assert assess(data)


@pytest.mark.parametrize('error', [OSError('synthetic'), subprocess.TimeoutExpired('pip-audit', 1)])
def test_audit_execution_failure_is_actionable(error):
    with patch('tools.dependency_audit.subprocess.run', side_effect=error):
        assert main() == 1


def test_clean_tool_report_passes_without_exceptions(capsys):
    data = {'dependencies': [{'name': 'synthetic', 'version': '1', 'vulns': []}]}
    with patch('tools.dependency_audit.subprocess.run', return_value=SimpleNamespace(stdout=json.dumps(data), returncode=0)):
        assert main() == 0
    assert 'EXCEPTION' not in capsys.readouterr().out


def test_installed_image_inventory_audit_does_not_resolve_other_dependencies(tmp_path):
    inventory = tmp_path / 'image.txt'
    inventory.write_text('pip==26.2.2\nsetuptools==84.1.0\n')
    data = {'dependencies': [{'name': 'pip', 'version': '26.2.2', 'vulns': []}]}
    with patch('tools.dependency_audit.subprocess.run', return_value=SimpleNamespace(stdout=json.dumps(data), returncode=0)) as run:
        assert main(str(inventory)) == 0
    command = run.call_args.args[0]
    assert command[command.index('-r') + 1] == str(inventory)
    assert '--no-deps' in command
    assert '--disable-pip' in command


def test_installed_image_unreviewed_advisory_still_blocks():
    data = report(identity='UNREVIEWED', name='pip', version='24.0')
    with patch('tools.dependency_audit.subprocess.run', return_value=SimpleNamespace(stdout=json.dumps(data), returncode=1)):
        assert main('synthetic-image.txt') == 1
