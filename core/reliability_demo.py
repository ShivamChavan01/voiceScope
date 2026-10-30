"""Synthetic, reproducible policy scenarios using the real deterministic checks."""

from core.reliability import PolicyRule, evaluate_reliability
from core.speakers import parse_speaker_turns


def demo_scenarios() -> list[dict]:
    policies = [
        PolicyRule(
            id='demo-refund-promise', title='Fictional demo refund policy',
            kind='no_same_day_refund_guarantee',
            text='Agents must never guarantee same-day refunds.',
        ),
        PolicyRule(
            id='demo-human-request', title='Fictional demo escalation policy',
            kind='honor_escalation_request',
            text='If a customer requests a supervisor, agents must honor the request immediately.',
        ),
    ]
    samples = [
        (
            'demo-review-compliant', 'refund timing and supervisor request',
            'Customer: When can I expect my refund?\n'
            'Agent: Refunds usually take five to seven business days. I cannot guarantee a same-day refund.\n'
            'Customer: I want to speak to a supervisor.\n'
            'Agent: I will connect you to a supervisor now.',
            'No supported policy patterns matched this synthetic conversation. Transfer completion is not verified.',
        ),
        (
            'demo-review-promise', 'same-day refund promise',
            'Customer: I need my money today. Can you guarantee that?\n'
            'Agent: I guarantee a same-day refund.\n'
            'Customer: Thank you.',
            'The synthetic agent makes an explicit promise forbidden by the fictional demo policy.',
        ),
        (
            'demo-review-escalation', 'request to speak to supervisor',
            'Customer: I want to speak to a supervisor.\n'
            'Agent: I cannot transfer you to a supervisor.\n'
            'Customer: That does not resolve my issue.',
            'The synthetic agent explicitly refuses a human request required by the fictional demo policy.',
        ),
    ]
    results = []
    for run_id, intent, transcript, summary in samples:
        turns = parse_speaker_turns(transcript)
        reliability = evaluate_reliability(turns, policies)
        results.append({
            'run_id': run_id,
            'data_source': 'synthetic_demo',
            'platform': 'synthetic',
            'status': 'completed',
            'evaluation_status': 'deterministic_checks_completed',
            'raw_transcript': transcript,
            'attributed_transcript': transcript,
            'transcript_speakers': turns,
            'reliability': reliability.model_dump(),
            'errors': [],
            'provider': {
                'name': 'synthetic', 'model': 'deterministic_rules',
                'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0,
            },
            'pipeline': {'stages_completed': ['synthetic_transcript', 'deterministic_reliability'], 'errors': []},
            'transcript_meta': {
                'word_count': len(transcript.split()), 'char_count': len(transcript),
                'duration_seconds': None, 'language': 'en',
            },
            'analysis': {
                'intent': intent, 'sentiment_arc': 'neutral', 'outcome': 'unresolved',
                'hallucination_detected': False, 'escalation_signal': False,
            },
            'report': {
                'quality_score': None,
                'executive_summary': summary,
                'key_findings': [finding.title for finding in reliability.findings],
                'recommendations': ['Inspect the exact quote and fictional policy snapshot.'],
            },
        })
    return results
