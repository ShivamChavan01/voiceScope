from core.reliability import ReliabilityReport
from core.reliability_demo import demo_scenarios


def test_demo_scenarios_are_repeatable_and_explicitly_synthetic():
    scenarios = demo_scenarios()
    assert scenarios == demo_scenarios()
    assert [scenario['run_id'] for scenario in scenarios] == [
        'demo-review-compliant', 'demo-review-promise', 'demo-review-escalation',
    ]
    for scenario in scenarios:
        assert scenario['data_source'] == 'synthetic_demo'
        assert scenario['provider']['name'] == 'synthetic'
        assert scenario['provider']['cost_usd'] == 0
        assert scenario['provider']['input_tokens'] == 0
        assert scenario['report']['quality_score'] is None
        assert 'harness' not in scenario
        assert scenario['transcript_meta']['duration_seconds'] is None
        report = ReliabilityReport.model_validate(scenario['reliability'])
        for policy in report.policy_snapshots:
            assert policy.title.startswith('Fictional demo')
        for finding in report.findings:
            for evidence in finding.evidence:
                assert evidence.quote in scenario['transcript_speakers'][evidence.turn_index]['text']


def test_demo_has_supported_no_match_guarantee_and_refusal_outcomes():
    no_match, guarantee, escalation = demo_scenarios()
    assert no_match['reliability']['status'] == 'assessed'
    assert no_match['reliability']['findings'] == []
    for scenario in [guarantee, escalation]:
        finding = scenario['reliability']['findings'][0]
        assert finding['category'] == 'policy_violation'
        assert finding['status'] == 'confirmed'
        assert finding['severity'] == 'high'
        assert scenario['analysis']['hallucination_detected'] is False
    assert guarantee['reliability']['findings'][0]['policy_id'] == 'demo-refund-promise'
    assert escalation['reliability']['findings'][0]['policy_id'] == 'demo-human-request'
