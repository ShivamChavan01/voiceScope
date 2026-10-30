"""Post-call transcript comparison. Automatic references measure disagreement, not truth."""

import re
import unicodedata
from collections import Counter
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

Role = Literal['caller', 'agent', 'unknown']
Scope = Literal['caller_only', 'mixed', 'unknown']


class AlignedInterval(TypedDict):
    start: float
    end: float
    segments: list[list['Segment']]


class Segment(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    text: str = Field(min_length=1, max_length=60000)
    speaker: str = Field(min_length=1, max_length=80)
    role: Role = 'unknown'
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)

    @model_validator(mode='after')
    def valid_time(self):
        if (self.start is None) != (self.end is None):
            raise ValueError('Both start and end are required for a timed segment')
        if self.start is not None and self.end <= self.start:
            raise ValueError('Segment end must follow start')
        if not self.text.strip():
            raise ValueError('Segment text cannot be blank')
        return self


class Transcript(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: Literal['bolna', 'deepgram', 'human']
    scope: Scope = 'unknown'
    segments: list[Segment] = Field(default_factory=list, max_length=2000)
    audio_sha256: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    human_verified: bool = Field(default=False, strict=True)
    verified_by: str | None = Field(default=None, max_length=120)

    @model_validator(mode='after')
    def valid_reference(self):
        if self.human_verified and (self.source != 'human' or not (self.verified_by or '').strip() or not self.audio_sha256):
            raise ValueError('Human verification needs a human source, reviewer, and recording hash')
        if self.source == 'human' and not self.human_verified:
            raise ValueError('Human references require explicit verification')
        if self.scope == 'caller_only' and any(segment.role == 'agent' for segment in self.segments):
            raise ValueError('Caller-only transcripts cannot include agent speech')
        if sum(len(segment.text) for segment in self.segments) > 120000:
            raise ValueError('Transcript exceeds comparison size limit')
        return self


class AudioInfo(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    available: bool = False
    sha256: str | None = None
    channels: int | None = Field(default=None, ge=1)
    duration_seconds: float | None = Field(default=None, gt=0)
    scope: Scope = 'unknown'
    scope_basis: str = 'Not established. Channel count alone does not identify speakers.'


class EditCounts(BaseModel):
    substitutions: int = 0
    deletions: int = 0
    insertions: int = 0
    reference_words: int = 0


class STTFinding(BaseModel):
    start: float | None
    end: float | None
    role: Role
    bolna_text: str
    reference_text: str
    category: list[str]
    severity: Literal['high', 'medium', 'low']
    status: Literal['confirmed_error', 'needs_review']
    confidence: Literal['high', 'low']
    confidence_basis: str
    explanation: str
    edits: EditCounts | None


class STTReview(BaseModel):
    schema_version: Literal['1'] = '1'
    status: Literal['completed', 'partial', 'blocked', 'failed'] = 'blocked'
    reference_source: str | None = None
    reference_human_verified: bool = False
    verified_by: str | None = None
    audio: AudioInfo = Field(default_factory=AudioInfo)
    metric_kind: Literal['wer', 'estimated_disagreement'] | None = None
    metric_value: float | None = None
    edits: EditCounts | None = None
    compared_groups: int = 0
    findings: list[STTFinding] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=lambda: [
        'Agreement between STT models does not prove transcription accuracy.',
        'Automatic reference discrepancies require human review. Confidence labels are evidence tiers, not calibrated probabilities.',
        'Meaning-change checks are bounded English heuristics and may miss paraphrases or entities.',
        'Timestamps identify aligned audio intervals, not exact word boundaries.',
    ])


_TOKEN = re.compile(r"(?:[$€£₹]\s*)?\d+(?:[.,/]\d+)*|[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


def words(text: str) -> list[str]:
    return [token.replace(' ', '') for token in _TOKEN.findall(unicodedata.normalize('NFKC', text).casefold().replace('’', "'"))]


def edit_counts(reference: str, hypothesis: str) -> EditCounts:
    """Levenshtein edits, with deterministic substitution-first ties and linear memory."""
    ref, hyp = words(reference), words(hypothesis)
    if max(len(ref), len(hyp)) > 800:
        raise ValueError('An aligned interval exceeds the 800-word comparison limit')
    previous = [(j, 0, 0, j) for j in range(len(hyp) + 1)]
    for i, token in enumerate(ref, 1):
        current = [(i, 0, i, 0)]
        for j, other in enumerate(hyp, 1):
            if token == other:
                current.append(previous[j - 1])
            else:
                cost, sub, delete, insert = previous[j - 1]
                substitution = (cost + 1, sub + 1, delete, insert)
                cost, sub, delete, insert = previous[j]
                deletion = (cost + 1, sub, delete + 1, insert)
                cost, sub, delete, insert = current[j - 1]
                insertion = (cost + 1, sub, delete, insert + 1)
                current.append(min((substitution, deletion, insertion), key=lambda item: item[0]))
        previous = current
    _, sub, delete, insert = previous[-1]
    return EditCounts(substitutions=sub, deletions=delete, insertions=insert, reference_words=len(ref))


def meaning_changes(reference: str, hypothesis: str) -> list[str]:
    ref, hyp = words(reference), words(hypothesis)
    difference = list((Counter(ref) - Counter(hyp)).elements()) + list((Counter(hyp) - Counter(ref)).elements())
    changed = set(difference)
    context = ' '.join(ref + hyp)
    categories = []
    if changed & {'no', 'not', 'never', 'cannot', "can't", "don't", "didn't", "won't", "isn't", "wasn't", "doesn't"}:
        categories.append('negation')
    if changed & {'cancel', 'book', 'renew', 'refund', 'accept', 'decline', 'stop', 'transfer', 'approve', 'reject'}:
        categories.append('user_intent')
    numbers = any(re.search(r'\d', token) for token in changed)
    if (changed & set('january february march april may june july august september october november december monday tuesday wednesday thursday friday saturday sunday today tomorrow yesterday'.split())
            or numbers and re.search(r'\b(?:date|birthday|appointment|scheduled|month|year)\b', context)):
        categories.append('date')
    if numbers and (re.search(r'[$€£₹]|\b(?:dollars?|rupees?|pounds?|amount|price|cost|usd|inr|eur|refund)\b', context)):
        categories.append('amount')
    if changed and re.search(r"\b(?:name is|i am|i'm|mr|mrs|ms|dr)\b", context):
        categories.append('name')
    if changed and re.search(r'\b(?:address|street|road|avenue|lane|apartment|postcode|zip)\b', context):
        categories.append('address')
    if numbers and not {'date', 'amount', 'address'} & set(categories):
        categories.append('number')
    return categories or ['wording']


def _finding(bolna: str, reference: str, role: Role, start, end, counts, verified: bool) -> STTFinding:
    categories = meaning_changes(reference, bolna)
    return STTFinding(
        start=start, end=end, role=role, bolna_text=bolna, reference_text=reference,
        category=categories, severity='high' if set(categories) & {'negation', 'amount', 'user_intent'} else 'medium' if categories != ['wording'] else 'low',
        status='confirmed_error' if verified else 'needs_review', confidence='high' if verified else 'low',
        confidence_basis='Human-verified reference with compatible speaker and time alignment.' if verified else 'Automatic reference or incomplete alignment; listen to the recording before concluding an error.',
        explanation='The Bolna transcript differs from the human-verified reference.' if verified else 'The transcripts disagree. An automatic reference or incomplete alignment requires review against the recording.', edits=counts,
    )


def compare_transcripts(bolna: Transcript, reference: Transcript, audio: AudioInfo) -> STTReview:
    result = STTReview(audio=audio, reference_source=reference.source, reference_human_verified=reference.human_verified, verified_by=reference.verified_by)
    if not audio.available or not audio.sha256:
        result.issues.append('Original recording is unavailable. No STT quality score was calculated.')
        return result
    if reference.audio_sha256 != audio.sha256:
        result.issues.append('Reference is not tied to this recording hash.')
        return result
    if audio.scope == 'unknown' or bolna.scope == 'unknown' or reference.scope == 'unknown':
        result.issues.append('Recording and transcript speaker coverage must be established before comparison.')
        return result
    if audio.scope == 'caller_only' and (bolna.scope != 'caller_only' or reference.scope != 'caller_only'):
        result.issues.append('Caller-only audio cannot validate a mixed-speaker transcript.')
        return result
    if not bolna.segments or not reference.segments:
        result.issues.append('One transcript is missing or empty; an empty reference is not ground truth.')
        return result
    # Caller-only Bolna output may be compared with a diarized mixed reference only after explicit role attribution.
    if any(segment.role == 'unknown' for segment in bolna.segments + reference.segments):
        result.issues.append('Unknown speaker roles prevent comparison. A diarization ID is not a caller identity.')
        return result
    target: set[Role] = {'caller'} if bolna.scope == 'caller_only' else {'caller', 'agent'}
    if bolna.scope == 'mixed' and reference.scope != 'mixed':
        result.issues.append('Unsegmented mixed-speaker speech cannot be compared with a caller-only reference.')
        return result
    original = [segment for segment in bolna.segments if segment.role in target]
    independent = [segment for segment in reference.segments if segment.role in target]
    if not original or not independent:
        result.issues.append('No speech for the requested speaker scope is available on both sides.')
        return result
    if any(segment.start is None or segment.end is None for segment in original + independent):
        result.status = 'partial'
        result.issues.append('Timestamps are missing. Only an unaligned text discrepancy is shown; no aggregate rate or confirmed error is available.')
        old, new = '\n'.join(segment.text for segment in original), '\n'.join(segment.text for segment in independent)
        if words(old) != words(new):
            result.findings.append(_finding(old, new, 'caller' if target == {'caller'} else 'unknown', None, None, None, False))
        return result
    if audio.duration_seconds and any(segment.end is not None and segment.end > audio.duration_seconds + 0.25 for segment in original + independent):
        result.issues.append('Transcript timestamps exceed the original recording duration.')
        return result
    # Intervals are grouped independently per role. Disjoint unmatched intervals remain insertions/deletions.
    totals = EditCounts()
    for role in sorted(target):
        events: list[tuple[float, float, int, Segment]] = []
        for side, segments in enumerate((original, independent)):
            for segment in segments:
                if segment.role == role:
                    start, end = segment.start, segment.end
                    assert start is not None and end is not None  # Validated before interval construction.
                    events.append((start, end, side, segment))
        events.sort(key=lambda item: (item[0], item[1], item[2]))
        groups: list[AlignedInterval] = []
        for start, end, side, segment in events:
            if groups and start < groups[-1]['end']:
                groups[-1]['end'] = max(groups[-1]['end'], end)
                groups[-1]['segments'][side].append(segment)
            else:
                groups.append({'start': start, 'end': end, 'segments': [[segment] if side == 0 else [], [segment] if side == 1 else []]})
        for group in groups:
            old, new = [' '.join(segment.text for segment in side) for side in group['segments']]
            try:
                counts = edit_counts(new, old)
            except ValueError:
                result.issues.append('An aligned interval exceeded the comparison size limit. Aggregate rate withheld.')
                continue
            result.compared_groups += 1
            for key in ('substitutions', 'deletions', 'insertions', 'reference_words'):
                setattr(totals, key, getattr(totals, key) + getattr(counts, key))
            if counts.substitutions + counts.deletions + counts.insertions:
                result.findings.append(_finding(old, new, role, group['start'], group['end'], counts, reference.human_verified))
    result.edits = totals
    result.status = 'partial' if result.issues else 'completed'
    if not result.issues and totals.reference_words:
        result.metric_kind = 'wer' if reference.human_verified else 'estimated_disagreement'
        result.metric_value = (totals.substitutions + totals.deletions + totals.insertions) / totals.reference_words
    else:
        result.status = 'partial'
        result.issues.append('No complete reference-word denominator is available; aggregate rate withheld.')
    return result
