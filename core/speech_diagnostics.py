"""Normalize documented Bolna measurements without inferring a network cause."""

import math
from typing import Literal

from pydantic import BaseModel, Field


class SpeechDiagnostics(BaseModel):
    source: Literal['bolna', 'unavailable'] = 'unavailable'
    time_to_first_audio_ms: float | None = None
    transcriber_ms: float | None = None
    llm_ms: float | None = None
    synthesizer_ms: float | None = None
    total_interruptions: int | None = None
    agent_interrupted_user_count: int | None = None
    user_interrupted_agent_count: int | None = None
    hangup_reason: str | None = None
    hangup_by: str | None = None
    limitations: list[str] = Field(default_factory=list)


def _measurement(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def _count(value) -> int | None:
    measured = _measurement(value)
    return int(measured) if measured is not None and measured.is_integer() else None


def _turn_mean(stage, field: str, nested: bool = False) -> float | None:
    if not isinstance(stage, dict) or not isinstance(stage.get('turns'), list):
        return None
    samples = []
    for turn in stage['turns']:
        if not isinstance(turn, dict) or turn.get('turn', 0) == -1:
            continue
        if nested:
            events = turn.get('turn_latency')
            if not isinstance(events, list):
                continue
            valid = [_measurement(item.get(field)) for item in events if isinstance(item, dict)]
            valid = [value for value in valid if value is not None]
            sample = valid[-1] if valid else None
        else:
            sample = _measurement(turn.get(field))
        if sample is not None:
            samples.append(sample)
    return round(sum(samples) / len(samples), 2) if samples else None


def bolna_speech_diagnostics(payload: dict) -> SpeechDiagnostics:
    latency = payload.get('latency_data')
    telephony = payload.get('telephony_data')
    telephony = telephony if isinstance(telephony, dict) else {}
    ending = {
        key: telephony.get(key) if isinstance(telephony.get(key), str) else None
        for key in ('hangup_reason', 'hangup_by')
    }
    if not isinstance(latency, dict):
        return SpeechDiagnostics(source='bolna' if any(ending.values()) else 'unavailable', **ending, limitations=[
            'Bolna timing and interruption measurements were not supplied for this call.',
            'A transcript alone cannot establish packet loss or a network fault.',
        ])
    interruptions = latency.get('interruption_stats')
    interruptions = interruptions if isinstance(interruptions, dict) else {}
    result = SpeechDiagnostics(
        source='bolna',
        time_to_first_audio_ms=_measurement(latency.get('time_to_first_audio')),
        transcriber_ms=_turn_mean(latency.get('transcriber'), 'audio_to_text_latency', nested=True),
        llm_ms=_turn_mean(latency.get('llm'), 'time_to_first_token'),
        synthesizer_ms=_turn_mean(latency.get('synthesizer'), 'time_to_first_token'),
        total_interruptions=_count(interruptions.get('total_interruptions')),
        agent_interrupted_user_count=_count(interruptions.get('agent_interrupted_user_count')),
        user_interrupted_agent_count=_count(interruptions.get('user_interrupted_agent_count')),
        **ending,
        limitations=[
            'Component timings are means across measured conversation turns, not a total response time.',
            'Speech recognition uses the last available latency event in each measured turn.',
            'Timings and silence alone do not establish a network fault.',
        ],
    )
    if any(value is None for value in (result.time_to_first_audio_ms, result.transcriber_ms, result.llm_ms, result.synthesizer_ms)):
        result.limitations.append('Some timing measurements are unavailable; missing values are not zero.')
    return result
