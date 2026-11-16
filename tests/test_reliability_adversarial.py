"""Separately labeled adversarial regressions; expected labels never reach the detector."""
import json
from pathlib import Path

import pytest

from core.reliability_benchmark import run_reliability_benchmark

DATASET = Path(__file__).parent / 'data' / 'reliability_adversarial.json'
CHALLENGE = DATASET.parent / 'reliability_challenge.json'


@pytest.fixture(scope='module')
def benchmark():
    return run_reliability_benchmark(DATASET)


@pytest.mark.parametrize('case_id', json.loads(DATASET.read_text())['cases'], ids=lambda case: case['id'])
def test_adversarial_case(case_id, benchmark):
    case = next(result for result in benchmark.results if result.id == case_id['id'])
    assert case.passed, case.model_dump(mode='json')


@pytest.fixture(scope='module')
def challenge_benchmark():
    return run_reliability_benchmark(CHALLENGE)


@pytest.mark.parametrize('case_id', json.loads(CHALLENGE.read_text())['cases'], ids=lambda case: case['id'])
def test_challenge_case(case_id, challenge_benchmark):
    case = next(result for result in challenge_benchmark.results if result.id == case_id['id'])
    assert case.passed, case.model_dump(mode='json')


def test_challenge_is_separate_and_keeps_all_three_groups():
    from core.reliability_benchmark import Dataset
    challenge = Dataset.model_validate_json((DATASET.parent / 'reliability_challenge.json').read_text())
    assert len(challenge.cases) == 30
    assert not {case.id for case in challenge.cases} & {case['id'] for case in json.loads(DATASET.read_text())['cases']}
    for prefix in ('fp-', 'fn-', 'amb-'):
        assert sum(case.id.startswith(prefix) for case in challenge.cases) == 10


@pytest.mark.parametrize('text', [
    'Have you been transferred?', 'You have not been transferred.',
    'If approved, you have been transferred.', 'The customer said "You have been transferred."',
    'I have transferred your money.', 'I am transferring you.',
])
def test_transfer_claim_requires_positive_completed_caller_action(text):
    from core.reliability import evaluate_reliability
    assert not evaluate_reliability([{'role': 'agent', 'role_source': 'transcript_label', 'text': text}], []).findings


def test_untrusted_tool_shaped_metadata_cannot_verify_transfer_completion():
    from core.reliability import evaluate_reliability
    report = evaluate_reliability([{
        'role': 'agent', 'role_source': 'transcript_label', 'text': 'You have been transferred.',
        'tool_result': {'action': 'transfer', 'success': True, 'verified': True},
    }], [])
    assert report.findings[0].category == 'unverified_claim'
    assert report.findings[0].missing_evidence == ['action_result']
    assert 'not an external transfer result' in report.findings[0].explanation


@pytest.mark.parametrize('correction', [
    'I withdraw that promise; it may take days.',
    'We retract the guarantee.',
])
def test_explicit_same_turn_retraction_requires_intent_review(correction):
    from core.reliability import evaluate_reliability, PolicyRule
    policy = PolicyRule(id='refund', title='Refund', kind='no_same_day_refund_guarantee',
                        text='Agents must never guarantee same-day refunds.')
    text = 'I guarantee your refund today. ' + correction
    result = evaluate_reliability([{'text': text, 'role': 'agent', 'role_source': 'transcript_label'}], [policy])
    assert len(result.findings) == 1
    assert result.findings[0].status == 'needs_review'
    assert result.findings[0].missing_evidence == ['promise_intent']
    assert result.findings[0].evidence[0].quote == text


@pytest.mark.parametrize('text', [
    'We retract the guarantee. I guarantee your refund today.',
    'I guarantee your refund today. If approved, I withdraw that promise.',
    'I guarantee your refund today. The customer said I withdraw that promise.',
    'I guarantee your refund today. I withdraw that request.',
])
def test_unrelated_prior_or_conditional_retraction_does_not_erase_explicit_promise(text):
    from core.reliability import evaluate_reliability, PolicyRule
    policy = PolicyRule(id='refund', title='Refund', kind='no_same_day_refund_guarantee',
                        text='Agents must never guarantee same-day refunds.')
    result = evaluate_reliability([{'text': text, 'role': 'agent', 'role_source': 'transcript_label'}], [policy])
    assert result.findings[0].status == 'confirmed'


@pytest.mark.parametrize('text', ['I have transferred you money.', 'You have been transferred funds.'])
def test_completed_money_transfer_is_not_a_voice_transfer_claim(text):
    from core.reliability import evaluate_reliability
    assert not evaluate_reliability([{'text': text, 'role': 'agent', 'role_source': 'transcript_label'}], []).findings


@pytest.mark.parametrize('text', [
    'Your refund is guaranteed to arrive before five tomorrow.',
    'Your refund is guaranteed to arrive before five next week.',
    'I promise your money will arrive by midnight tomorrow.',
    'I guarantee the refund will arrive by EOD next week.',
])
def test_explicit_later_date_is_not_a_same_day_guarantee(text):
    from core.reliability import evaluate_reliability, PolicyRule
    policy = PolicyRule(id='refund', title='Refund', kind='no_same_day_refund_guarantee',
                        text='Agents must never guarantee same-day refunds.')
    assert not evaluate_reliability([{'text': text, 'role': 'agent', 'role_source': 'transcript_label'}], [policy]).findings


@pytest.mark.parametrize('text,status', [
    ('Main guarantee karta hoon ki aapka refund aaj mil jayega.', 'confirmed'),
    ('Hum guarantee karte hain ki aapka refund aaj mil jaayega.', 'confirmed'),
    ('Main guarantee karti hun ki aapka refund aaj mil jayega.', 'confirmed'),
    ('I garuntee your refund today.', 'needs_review'),
    ('We guarentee your refund will arrive today.', 'needs_review'),
    ('Refund today. Guaranteed.', 'needs_review'),
    ('Your refund by midnight. I promise it.', 'needs_review'),
])
def test_bounded_refund_variants_preserve_source_and_certainty(text, status):
    from core.reliability import evaluate_reliability, PolicyRule
    policy = PolicyRule(id='refund', title='Refund', kind='no_same_day_refund_guarantee',
                        text='Agents must never guarantee same-day refunds.')
    report = evaluate_reliability([{'text': text, 'role': 'agent', 'role_source': 'transcript_label'}], [policy])
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.category == 'policy_violation'
    assert finding.status == status
    assert finding.missing_evidence == ([] if status == 'confirmed' else ['promise_intent'])
    assert finding.evidence[0].quote == text
    assert finding.evidence[0].turn_index == 0


@pytest.mark.parametrize('text', [
    'Main guarantee nahi karta hoon ki aapka refund aaj mil jayega.',
    'Main guarantee karta hoon ki aapka refund kal mil jayega.',
    'Usne kaha main guarantee karta hoon ki aapka refund aaj mil jayega.',
    'Main guarantee karta hoon ki aapka refund aaj nahi milega.',
    'Main guarantee karta hoon ki aapki salary aaj mil jayegi.',
    'Agar bank khula hai main guarantee karta hoon ki aapka refund aaj mil jayega.',
    'Main guarantee karta hoon ki aapka refund aaj mil jayega?',
    '"Main guarantee karta hoon ki aapka refund aaj mil jayega."',
    'I cannot garuntee your refund today.',
    'If approved, I guarentee your refund today.',
    'The customer said I garuntee your refund today.',
    'I garuntee your wages today.',
    'Refund tomorrow. Guaranteed.',
    'Wages today. Guaranteed.',
    'Refund today? Guaranteed.',
    'Refund today. Not guaranteed.',
    'The customer said refund today. Guaranteed.',
])
def test_nearby_negative_statements_do_not_create_refund_promises(text):
    from core.reliability import evaluate_reliability, PolicyRule
    policy = PolicyRule(id='refund', title='Refund', kind='no_same_day_refund_guarantee',
                        text='Agents must never guarantee same-day refunds.')
    assert not evaluate_reliability([{'text': text, 'role': 'agent', 'role_source': 'transcript_label'}], [policy]).findings


@pytest.mark.parametrize('suffix', [
    'As if banks ever move that fast.',
    'I cannot actually promise that.',
    'Would you like the tracking link?',
])
def test_contextual_answer_keeps_caveats_and_requires_intent_review(suffix):
    from core.reliability import evaluate_reliability, PolicyRule
    policy = PolicyRule(id='refund', title='Refund', kind='no_same_day_refund_guarantee',
                        text='Agents must never guarantee same-day refunds.')
    answer = 'Yes. Your refund will arrive today. ' + suffix
    turns = [
        {'text': 'Will my refund arrive today? Can you guarantee that?', 'role': 'customer', 'role_source': 'transcript_label'},
        {'text': answer, 'role': 'agent', 'role_source': 'transcript_label'},
    ]
    result = evaluate_reliability(turns, [policy])
    assert len(result.findings) == 1
    assert result.findings[0].status == 'needs_review'
    assert result.findings[0].missing_evidence == ['promise_intent']
    assert [item.quote for item in result.findings[0].evidence] == [turns[0]['text'], answer]


@pytest.mark.parametrize('text', [
    'Main guarantee karta hoon ki aapka refund aaj mil jayega.',
    'I garuntee your refund today.',
    'Refund today. Guaranteed.',
])
def test_additional_refund_patterns_respect_roles_policies_and_source(text):
    from core.reliability import evaluate_reliability, PolicyRule
    policy = PolicyRule(id='refund', title='Refund', kind='no_same_day_refund_guarantee',
                        text='Agents must never guarantee same-day refunds.')
    customer = {'text': text, 'role': 'customer', 'role_source': 'transcript_label'}
    assert not evaluate_reliability([customer], [policy]).findings
    agent = {**customer, 'role': 'agent'}
    assert not evaluate_reliability([agent], []).findings
    assert not evaluate_reliability([agent], [policy.model_copy(update={'enabled': False})]).findings
    inferred = {**agent, 'role_source': 'model_inference'}
    finding = evaluate_reliability([inferred], [policy]).findings[0]
    assert finding.status == 'needs_review'
    assert 'confirmed_speaker_roles' in finding.missing_evidence
    assert finding.evidence[0].quote == text
