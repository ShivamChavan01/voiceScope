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
    segments = []
    for word in result.words:
        text = word.get('punctuated_word') or word.get('word')
        if not isinstance(text, str) or not text.strip():
            continue
        speaker = f"dg_{word['speaker']}" if isinstance(word.get('speaker'), int) else 'dg_unknown'
        # Missing or invalid provider timing remains absent; the comparison cannot score it.
        start, end = word.get('start'), word.get('end')
        valid = all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 for value in (start, end)) and end > start
        if segments and segments[-1].speaker == speaker and (segments[-1].start is not None) == valid and (not valid or start - segments[-1].end <= 0.75) and not segments[-1].text.endswith(('.', '?', '!')):
            segments[-1].text += ' ' + text
            if valid:
                segments[-1].end = end
        else:
            segments.append(Segment(text=text, speaker=speaker, start=start if valid else None, end=end if valid else None))
    if not segments and result.transcript.strip():
        segments = [Segment(text=result.transcript, speaker='dg_unknown')]
    return Transcript(source='deepgram', scope='unknown', audio_sha256=audio_sha256, segments=segments)


def validate_bolna_annotations(original: Transcript, annotated: Transcript) -> Transcript:
    if annotated.source != 'bolna':
        raise ValueError('Annotations must describe the Bolna transcript')
    def by_role(document):
        return {role: words(' '.join(segment.text for segment in document.segments if segment.role == role)) for role in ('caller', 'agent', 'unknown')}
    if by_role(original) != by_role(annotated):
        raise ValueError('Timing annotations must preserve the original Bolna words and roles')
    return annotated
