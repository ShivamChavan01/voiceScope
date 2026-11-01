"""Explicit transcript source adapters. No timing or caller identity is invented."""

import math

from core.speakers import parse_speaker_turns
from core.stt_quality import Segment, Transcript, words
from stt_providers.base import TranscriptionResult


def bolna_transcript(text: str) -> Transcript:
    turns = parse_speaker_turns(text)
    if not turns:
        return Transcript(source='bolna', segments=[Segment(text=text, speaker='unknown')] if text.strip() else [])
    segments = [Segment(text=turn['text'], speaker=str(turn['speaker']), role='caller' if turn['role'] == 'customer' else 'agent' if turn['role'] == 'agent' else 'unknown') for turn in turns if turn['text'].strip()]
    roles = {segment.role for segment in segments}
    return Transcript(source='bolna', scope='unknown' if 'unknown' in roles else 'mixed' if 'agent' in roles else 'caller_only', segments=segments)


def deepgram_reference(result: TranscriptionResult, audio_sha256: str) -> Transcript:
    segments: list[Segment] = []
    for word in result.words:
        text = word.get('punctuated_word') or word.get('word')
        if not isinstance(text, str) or not text.strip():
            continue
        speaker = f"dg_{word['speaker']}" if isinstance(word.get('speaker'), int) else 'dg_unknown'
        # Missing or invalid provider timing remains absent; the comparison cannot score it.
        raw_start, raw_end = word.get('start'), word.get('end')
        start = raw_start if isinstance(raw_start, (int, float)) and not isinstance(raw_start, bool) and math.isfinite(raw_start) and raw_start >= 0 else None
        end = raw_end if isinstance(raw_end, (int, float)) and not isinstance(raw_end, bool) and math.isfinite(raw_end) and raw_end >= 0 else None
        if start is None or end is None or end <= start:
            start, end = None, None
        previous = segments[-1] if segments else None
        if previous and previous.speaker == speaker and (previous.start is not None) == (start is not None) and (start is None or previous.end is not None and start - previous.end <= 0.75) and not previous.text.endswith(('.', '?', '!')):
            segments[-1].text += ' ' + text
            segments[-1].end = end
        else:
            segments.append(Segment(text=text, speaker=speaker, start=start, end=end))
    if not segments and result.transcript.strip():
        segments = [Segment(text=result.transcript, speaker='dg_unknown')]
    return Transcript(source='deepgram', scope='unknown', audio_sha256=audio_sha256, segments=segments)


def validate_bolna_annotations(original: Transcript, annotated: Transcript) -> Transcript:
    if original.source not in ('bolna', 'synthetic') or annotated.source != original.source:
        raise ValueError('Annotations must describe the Bolna transcript')
    def by_role(document):
        return {role: words(' '.join(segment.text for segment in document.segments if segment.role == role)) for role in ('caller', 'agent', 'unknown')}
    if by_role(original) != by_role(annotated):
        raise ValueError('Timing annotations must preserve the original Bolna words and roles')
    return annotated
