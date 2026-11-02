import pytest
from pydantic import ValidationError

from core.reliability import PolicyRule, evaluate_reliability


def refund_policy(**updates):
    return PolicyRule(**{
        'id': 'refund', 'title': 'Refund promises', 'kind': 'no_same_day_refund_guarantee',
        'text': 'Agents must never guarantee same-day refunds.', **updates,
    })


def escalation_policy():
    return PolicyRule(id='escalation', title='Human requests', kind='honor_escalation_request',
                      text='If a customer requests a supervisor, agents must honor the request immediately.')


def turn(text, role='agent', source='transcript_label'):
    return {'text': text, 'role': role, 'role_source': source}


def test_forbidden_guarantee_has_exact_quote_snapshot_and_stable_identity():
    turns = [turn('Hello. I guarantee a same-day refund. Thank you.')]
    policy = refund_policy()
    report = evaluate_reliability(turns, [policy])
    finding = report.findings[0]
    assert report.status == 'assessed'
    assert finding.category == 'policy_violation'
    assert finding.status == 'confirmed'
    assert finding.policy_id == 'refund'
    assert finding.evidence[0].turn_index == 0
    assert finding.evidence[0].quote == 'I guarantee a same-day refund.'
    assert finding.evidence[0].quote in turns[0]['text']
    assert report.policy_snapshots[0].text == policy.text
    assert report == evaluate_reliability(turns, [policy])


@pytest.mark.parametrize('text', [
    'I cannot guarantee a same-day refund.',
    "I don't promise a refund today.",
    'Your refund is not guaranteed today.',
    'Can I guarantee a same-day refund?',
    'If it is approved, I guarantee a same-day refund.',
    'I could guarantee a same-day refund.',
    'For example, "I guarantee a same-day refund."',
    "The customer said 'I guarantee a same-day refund.'",
    'I will process your refund today.',
    'Your refund normally takes five days.',
    'I guarantee I will process your refund today.',
])
def test_negated_hypothetical_reported_and_processing_estimates_do_not_confirm(text):
    assert evaluate_reliability([turn(text)], [refund_policy()]).findings == []


def test_customer_guarantee_and_disabled_policy_do_not_trigger():
    assert not evaluate_reliability([turn('I guarantee a same-day refund.', 'customer')], [refund_policy()]).findings
    report = evaluate_reliability([turn('I guarantee a same-day refund.')], [refund_policy(enabled=False)])
    assert report.status == 'insufficient_evidence'
    assert report.checked_rule_ids == []
    assert not report.findings


@pytest.mark.parametrize('source', ['model_inference', 'unknown', None])
def test_uncertain_agent_role_downgrades_policy_match(source):
    finding = evaluate_reliability([turn('I guarantee a same-day refund.', source=source)], [refund_policy()]).findings[0]
    assert finding.status == 'needs_review'
    assert finding.missing_evidence == ['confirmed_speaker_roles']


def test_refund_completion_without_tool_result_is_only_unverified():
    report = evaluate_reliability([turn("I've processed your refund.")], [])
    assert report.status == 'insufficient_evidence'
    finding = report.findings[0]
    assert finding.category == 'unverified_claim'
    assert finding.status == 'needs_review'
    assert finding.policy_id is None
    assert finding.missing_evidence == ['action_result']
    assert 'does not mean the refund failed' in finding.explanation


@pytest.mark.parametrize('text', [
    "I haven't processed your refund.",
    'Have I processed your refund?',
    'If approved, your refund is processed.',
    'Your refund is being processed.',
    'I can process your refund.',
])
def test_refund_questions_negations_and_futures_are_not_completion_claims(text):
    assert evaluate_reliability([turn(text)], []).findings == []


def test_no_blanket_missing_tool_warning_on_ordinary_call():
    report = evaluate_reliability([turn('How can I help?')], [refund_policy()])
    assert report.status == 'assessed'
    assert report.findings == []
    assert not any('tool' in limitation for limitation in report.limitations)


def test_escalation_refusal_requires_customer_request_and_following_refusal():
    turns = [turn('Can I speak to a supervisor?', 'customer'), turn('I cannot transfer you to a supervisor.')]
    report = evaluate_reliability(turns, [escalation_policy()])
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.status == 'confirmed'
    assert [e.turn_index for e in finding.evidence] == [0, 1]
    assert all(e.quote in turns[e.turn_index]['text'] for e in finding.evidence)


@pytest.mark.parametrize('turns', [
    [turn('Can I speak to a supervisor?', 'customer'), turn('I will connect you now.')],
    [turn('Can I speak to a supervisor?', 'customer'), turn('Please wait.')],
    [turn('I cannot transfer you to a supervisor.')],
    [turn('I do not want to speak to a supervisor.', 'customer'), turn('I cannot transfer you.')],
    [turn('Can I speak to a supervisor?', 'agent'), turn('I cannot transfer you.', 'customer')],
    [turn('Can I speak to a supervisor?', 'customer'), turn('Never mind.', 'customer'), turn('I cannot transfer you.')],
    [turn('Can I speak to a supervisor?', 'customer'), turn('I will transfer you.'), turn('I cannot transfer you.')],
])
def test_missing_transfer_evidence_and_wrong_role_are_not_refusals(turns):
    assert evaluate_reliability(turns, [escalation_policy()]).findings == []


def test_inferred_request_downgrades_escalation_finding():
    report = evaluate_reliability([
        turn('I want to speak to a supervisor.', 'customer', 'model_inference'),
        turn('I cannot transfer you.'),
    ], [escalation_policy()])
    assert report.findings[0].status == 'needs_review'


@pytest.mark.parametrize('turns', [[], [{}], [{'text': None}], [{'text': ''}], [None]])
def test_missing_or_malformed_turns_are_insufficient(turns):
    report = evaluate_reliability(turns, [refund_policy()])
    assert report.status == 'insufficient_evidence'
    assert report.findings[0].category == 'insufficient_evidence'
    assert report.findings[0].evidence == []


def test_policy_version_is_computed_immutable_and_independent_of_title():
    rule = refund_policy(id=' refund ', title=' Refund promises ')
    assert rule.id == 'refund'
    assert rule.title == 'Refund promises'
    assert len(rule.version) == 64
    assert refund_policy(title='Another title').version == rule.version
    assert refund_policy(text='Agents must never promise same-day refunds.').version != rule.version
    assert refund_policy(version='forged').version == rule.version
    with pytest.raises(ValidationError):
        rule.text = 'Updated'


@pytest.mark.parametrize('updates', [
    {'id': ''}, {'title': '  '}, {'text': ''}, {'kind': 'unsupported'}, {'enabled': 'false'},
    {'text': 'Agents may guarantee same-day refunds.'},
    {'text': 'Agents cannot guarantee same-day refunds unless a manager approves.'},
    {'text': 'Refunds take five days.'},
])
def test_invalid_or_nonprohibitive_policy_is_rejected(updates):
    with pytest.raises(ValidationError):
        refund_policy(**updates)


def test_nonobligatory_escalation_policy_is_rejected():
    with pytest.raises(ValidationError):
        PolicyRule(id='escalation', title='Guidance', kind='honor_escalation_request',
                   text='Customers can ask questions about supervisors.')


def test_unknown_role_with_inconsistent_provenance_never_confirms():
    report = evaluate_reliability([turn('I guarantee a same-day refund.', 'unknown')], [refund_policy()])
    assert report.status == 'insufficient_evidence'
    assert report.findings[0].status == 'needs_review'


@pytest.mark.parametrize('refusal', [
    'If I cannot transfer you, I will ask someone to call.',
    'The previous agent said I cannot transfer you.',
    'For example I cannot transfer you.',
])
def test_hypothetical_or_reported_refusal_is_not_confirmed(refusal):
    report = evaluate_reliability([
        turn('I want to speak to a supervisor.', 'customer'), turn(refusal),
    ], [escalation_policy()])
    assert report.findings == []


def test_hypothetical_request_is_not_an_actual_request():
    report = evaluate_reliability([
        turn('If I want to speak to a supervisor, what happens?', 'customer'), turn('I cannot transfer you.'),
    ], [escalation_policy()])
    assert report.findings == []


@pytest.mark.parametrize('text', [
    'Agents must never guarantee delivery. Same-day refunds are allowed.',
    'Agents must never guarantee same-day delivery. Refunds may take five days.',
])
def test_refund_policy_prohibition_must_refer_to_refund_guarantee(text):
    with pytest.raises(ValidationError):
        refund_policy(text=text)


@pytest.mark.parametrize('text', [
    'If a customer requests a supervisor, agents must not honor the request.',
    'Do not honor customer requests to speak to a human.',
    'A customer requests a supervisor. Agents must honor vacation requests.',
])
def test_opposite_or_unrelated_escalation_obligation_is_not_activated(text):
    with pytest.raises(ValidationError):
        PolicyRule(id='escalation', title='Guidance', kind='honor_escalation_request', text=text)


@pytest.mark.parametrize('text', [
    'I promise no same-day refunds.',
    "I guarantee same-day refunds aren't available.",
    'I promise to explain why same-day refunds are impossible.',
    'I promise to help you ask for a refund today.',
])
def test_guarantee_must_commit_to_positive_refund_outcome(text):
    assert evaluate_reliability([turn(text)], [refund_policy()]).findings == []


@pytest.mark.parametrize('text', [
    'I cannot transfer you to billing, but I will connect you to a supervisor.',
    'I cannot transfer you directly, so I will connect you to a supervisor.',
    'I cannot transfer you to billing.',
])
def test_refusal_must_target_requested_human_and_respect_alternative_offer(text):
    assert evaluate_reliability([
        turn('I want to speak to a supervisor.', 'customer'), turn(text),
    ], [escalation_policy()]).findings == []


@pytest.mark.parametrize('text', [
    'I have processed your refund request.',
    'I completed the refund application.',
    'I issued a refund request.',
    'Your refund is processed only after approval.',
])
def test_administrative_or_conditional_refund_steps_are_not_completed_actions(text):
    assert evaluate_reliability([turn(text)], []).findings == []


@pytest.mark.parametrize('text', [
    'Agents must never guarantee same-day refunds. Agents are allowed to guarantee same-day refunds.',
    'Agents must never promise free shipping, but may offer same-day refunds.',
])
def test_contradictory_or_unrelated_policy_is_rejected(text):
    with pytest.raises(ValidationError):
        refund_policy(text=text)


def test_negated_escalation_obligation_with_adverb_is_rejected():
    with pytest.raises(ValidationError):
        PolicyRule(id='escalation', title='Wrong obligation', kind='honor_escalation_request',
                   text='If a customer requests a supervisor, agents must not automatically honor the request.')


def test_alternative_nonhuman_department_does_not_erase_explicit_supervisor_refusal():
    report = evaluate_reliability([
        turn('I want to speak to a supervisor.', 'customer'),
        turn('I will transfer you to billing, but I cannot transfer you to a supervisor.'),
    ], [escalation_policy()])
    assert report.findings[0].category == 'policy_violation'
    assert report.findings[0].status == 'confirmed'


@pytest.mark.parametrize('statement', [
    'I cannot transfer money between accounts.',
    'I cannot transfer funds.',
    'I cannot connect the payment system.',
    'I cannot transfer your balance to a supervisor.',
])
def test_escalation_refusal_does_not_include_unrelated_transfer_objects(statement):
    result = evaluate_reliability([
        turn('Please transfer me to a supervisor.', 'customer'), turn(statement),
    ], [escalation_policy()])
    assert not result.findings


@pytest.mark.parametrize('statement', [
    'I guarantee your refund today, not tomorrow.',
    'I promise your refund today, not next week.',
    'Your refund is guaranteed today, not tomorrow.',
])
def test_unrelated_negated_time_does_not_erase_affirmative_refund_guarantee(statement):
    result = evaluate_reliability([turn(statement)], [refund_policy()])
    assert len(result.findings) == 1
    assert result.findings[0].status == 'confirmed'


@pytest.mark.parametrize('statement', [
    'I cannot transfer money, but I cannot transfer you to a supervisor either.',
    'I cannot connect the payment system; I cannot connect you to a supervisor.',
])
def test_unrelated_refusal_does_not_hide_a_later_actual_escalation_refusal(statement):
    result = evaluate_reliability([
        turn('Please transfer me to a supervisor.', 'customer'), turn(statement),
    ], [escalation_policy()])
    assert len(result.findings) == 1
    assert result.findings[0].status == 'confirmed'


def test_transfer_you_money_is_not_a_refusal_to_transfer_the_caller():
    result = evaluate_reliability([
        turn('Please transfer me to a supervisor.', 'customer'),
        turn('I cannot transfer you money.'),
    ], [escalation_policy()])
    assert not result.findings


@pytest.mark.parametrize('statement', [
    'I guarantee your refund today, said the previous agent.',
    'Your refund is guaranteed today, as an example.',
])
def test_reported_or_example_suffix_does_not_become_a_confirmed_guarantee(statement):
    assert not evaluate_reliability([turn(statement)], [refund_policy()]).findings

@pytest.mark.parametrize('text,expected', [
    ('I assure you your refund will arrive today.', True),
    ('I assure you that your refund will arrive today.', True),
    ('I assure you your refund might arrive today.', False),
    ('I cannot assure you your refund will arrive today.', False),
    ('If approved, I assure you your refund will arrive today.', False),
    ('The agent said I assure you your refund will arrive today.', False),
    ('"I assure you your refund will arrive today."', False),
    ('Refunds usually arrive today.', False),
])
def test_assurance_guarantees_remain_bounded(text, expected):
    findings = evaluate_reliability([turn(text)], [refund_policy()]).findings
    assert any(f.category == 'policy_violation' for f in findings) is expected


@pytest.mark.parametrize('refusal,expected', [
    ('I will not let you speak with the team lead.', True),
    ('I cannot transfer you to the team lead.', True),
    ('I will transfer you to the team lead.', False),
    ('I cannot transfer you money.', False),
    ('I cannot transfer your money to the team lead.', False),
    ('I said "I will not let you speak with the team lead."', False),
    ('If unavailable, I will not let you speak with the team lead.', False),
])
def test_team_lead_request_and_refusal_with_financial_guards(refusal, expected):
    findings = evaluate_reliability([turn('Please let me speak with your team lead.', 'customer'), turn(refusal)], [escalation_policy()]).findings
    assert any(f.category == 'policy_violation' for f in findings) is expected


@pytest.mark.parametrize('text,expected', [
    ('The money has been returned to your card.', True),
    ('The money has not been returned to your card.', False),
    ('The money will be returned to your card.', False),
    ('The money might have been returned to your card.', False),
    ('The money has been transferred to your card.', False),
    ('The customer said the money has been returned to your card.', False),
    ('"The money has been returned to your card."', False),
])
def test_returned_money_is_an_unverified_claim_not_a_confirmed_action(text, expected):
    findings = evaluate_reliability([turn(text)], []).findings
    claims = [f for f in findings if f.category == 'unverified_claim']
    assert bool(claims) is expected
    if claims:
        assert claims[0].status == 'needs_review'
        assert claims[0].missing_evidence == ['action_result']


def test_assurance_by_customer_is_not_an_agent_violation():
    assert not evaluate_reliability([turn('I assure you your refund will arrive today.', 'customer')], [refund_policy()]).findings
