import pytest

from core.speech_diagnostics import bolna_speech_diagnostics


def test_real_shaped_diagnostics_mean_conversation_turns_not_welcome():
    result = bolna_speech_diagnostics({
        'latency_data': {
            'time_to_first_audio': 136.2,
            'transcriber': {'turns': [
                {'turn': 1, 'turn_latency': [{'audio_to_text_latency': 100}, {'audio_to_text_latency': 200}]},
                {'turn': 2, 'turn_latency': [{'audio_to_text_latency': 400}]},
            ]},
            'llm': {'turns': [{'turn': 1, 'time_to_first_token': 200}, {'turn': 2, 'time_to_first_token': 400}]},
            'synthesizer': {'turns': [{'turn': -1, 'time_to_first_token': 9999}, {'turn': 1, 'time_to_first_token': 100}]},
            'interruption_stats': {'total_interruptions': 0, 'agent_interrupted_user_count': 0, 'user_interrupted_agent_count': 0},
        },
        'telephony_data': {'hangup_by': 'Caller', 'hangup_reason': 'Unknown'},
    })
    assert result.source == 'bolna'
    assert result.time_to_first_audio_ms == 136.2
    assert result.transcriber_ms == 300
    assert result.llm_ms == 300
    assert result.synthesizer_ms == 100
    assert result.total_interruptions == 0
    assert result.hangup_by == 'Caller'
    assert any('not a total' in item for item in result.limitations)


@pytest.mark.parametrize('invalid', [-1, float('nan'), float('inf'), True, '200', None, []])
def test_invalid_measurements_are_unavailable(invalid):
    result = bolna_speech_diagnostics({'latency_data': {
        'time_to_first_audio': invalid,
        'llm': {'turns': [{'turn': 1, 'time_to_first_token': invalid}]},
        'interruption_stats': {'total_interruptions': invalid},
    }})
    assert result.time_to_first_audio_ms is None
    assert result.llm_ms is None
    assert result.total_interruptions is None


@pytest.mark.parametrize('payload', [{}, {'latency_data': None}, {'latency_data': []}])
def test_missing_diagnostics_do_not_claim_zero_or_network_failure(payload):
    result = bolna_speech_diagnostics(payload)
    assert result.source == 'unavailable'
    assert result.time_to_first_audio_ms is None
    assert result.total_interruptions is None


def test_malformed_nested_data_is_safe_and_fractional_counts_are_not_rounded():
    result = bolna_speech_diagnostics({'latency_data': {
        'transcriber': {'turns': [None, {'turn_latency': None}]},
        'llm': [], 'synthesizer': {'turns': 'bad'},
        'interruption_stats': {'total_interruptions': 1.5},
    }, 'telephony_data': None})
    assert result.total_interruptions is None
    assert result.transcriber_ms is None
    assert result.hangup_reason is None


def test_hangup_evidence_is_retained_when_timings_are_missing():
    result = bolna_speech_diagnostics({'telephony_data': {
        'hangup_by': 'Caller', 'hangup_reason': 'Network failure',
    }})
    assert result.source == 'bolna'
    assert result.hangup_by == 'Caller'
    assert result.hangup_reason == 'Network failure'
    assert result.time_to_first_audio_ms is None
    assert result.total_interruptions is None
