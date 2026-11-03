"""Conservative text correspondence for automatic references, never verified WER.

Sources are immutable. Positions in findings come from reference speech or its
neighbouring anchors; they are not reconstructed original Bolna timestamps.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from core.stt_quality import (
    AudioInfo, AutomaticAlignment, EditCounts, SpeakerAnchorEvidence, STTReview,
    Transcript, _finding, compare_transcripts, words,
)

KnownRole = Literal['caller', 'agent']


@dataclass(frozen=True)
class Token:
    text: str
    segment: int


def _tokens(document: Transcript) -> list[Token]:
    return [Token(word, index) for index, segment in enumerate(document.segments) for word in words(segment.text)]


def _phrases(tokens: list[Token], document: Transcript) -> dict[tuple[str, ...], list[int]]:
    phrases: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index in range(len(tokens) - 3):
        block = tokens[index:index + 4]
        speakers = {document.segments[token.segment].speaker for token in block}
        roles = {document.segments[token.segment].role for token in block}
        if len(speakers) == len(roles) == 1:
            phrases[tuple(token.text for token in block)].append(index)
    return phrases


def _speaker_map(original: Transcript, reference: Transcript, left: list[Token], right: list[Token], bounded: set[int]):
    old_phrases, new_phrases = _phrases(left, original), _phrases(right, reference)
    votes: dict[str, dict[KnownRole, set[int]]] = {
        segment.speaker: {'caller': set(), 'agent': set()} for segment in reference.segments}
    pairs: list[tuple[str, KnownRole, int, int]] = []
    for phrase, starts in old_phrases.items():
        matches = new_phrases.get(phrase, [])
        if len(starts) != 1 or len(matches) != 1:
            continue
        if any(right[index].segment not in bounded for index in range(matches[0], matches[0] + 4)):
            continue
        role = original.segments[left[starts[0]].segment].role
        speaker = reference.segments[right[matches[0]].segment].speaker
        if role in ('caller', 'agent'):
            votes[speaker][role].update(range(matches[0], matches[0] + 4))
            pairs.extend((speaker, role, starts[0] + offset, matches[0] + offset) for offset in range(4))
    evidence = []
    for speaker in sorted(votes):
        if speaker == 'dg_unknown':
            return [], []
        counts = votes[speaker]
        winner: KnownRole = 'caller' if len(counts['caller']) > len(counts['agent']) else 'agent'
        loser: KnownRole = 'agent' if winner == 'caller' else 'caller'
        support, competing = len(counts[winner]), len(counts[loser])
        if support < 12 or support / (support + competing) < .9:
            return [], []
        evidence.append(SpeakerAnchorEvidence(speaker=speaker, role=winner, matched_words=support, competing_words=competing))
    return evidence, pairs


def _path(reference: list[Token], hypothesis: list[Token]) -> list[tuple[int | None, int | None]]:
    """Bounded Levenshtein backtrace with the existing substitution-first tie rule."""
    width = len(hypothesis) + 1
    trace = bytearray((len(reference) + 1) * width)
    previous = list(range(width))
    for j in range(1, width):
        trace[j] = 3
    for i, token in enumerate(reference, 1):
        current = [i]
        trace[i * width] = 2
        for j, other in enumerate(hypothesis, 1):
            if token.text == other.text:
                current.append(previous[j - 1])
            else:
                costs = (previous[j - 1] + 1, previous[j] + 1, current[j - 1] + 1)
                operation = min(range(3), key=costs.__getitem__)
                current.append(costs[operation])
                trace[i * width + j] = operation + 1
        previous = current
    result: list[tuple[int | None, int | None]] = []
    i, j = len(reference), len(hypothesis)
    while i or j:
        operation = trace[i * width + j]
        if operation in (0, 1):
            i, j = i - 1, j - 1
            result.append((i, j))
        elif operation == 2:
            i -= 1
            result.append((i, None))
        else:
            j -= 1
            result.append((None, j))
    return list(reversed(result))


def _counts(path, reference: list[Token], hypothesis: list[Token]) -> EditCounts:
    return EditCounts(
        substitutions=sum(i is not None and j is not None and reference[i].text != hypothesis[j].text for i, j in path),
        deletions=sum(j is None for i, j in path),
        insertions=sum(i is None for i, j in path),
        reference_words=sum(i is not None for i, j in path),
    )


def _quotes(tokens: list[Token], indices: list[int], document: Transcript) -> str:
    return '\n'.join(document.segments[index].text for index in sorted({tokens[i].segment for i in indices}))


def compare_with_automatic_alignment(original: Transcript, reference: Transcript, audio: AudioInfo) -> STTReview:
    strict = compare_transcripts(original, reference, audio)
    if strict.metric_value is not None or reference.source != 'deepgram' or reference.human_verified:
        return strict

    def blocked(reason: str) -> STTReview:
        strict.issues.append(reason)
        return strict

    if not audio.available or not audio.sha256 or reference.audio_sha256 != audio.sha256:
        return blocked('Automatic alignment requires the matching original recording.')
    if original.audio_sha256 and original.audio_sha256 != audio.sha256:
        return blocked('Original transcript recording hash does not match.')
    if original.source != 'bolna' or original.scope != 'mixed' or audio.scope == 'caller_only' or reference.scope == 'caller_only':
        return blocked('Automatic alignment supports complete mixed Bolna conversations only.')
    if any(segment.role == 'unknown' for segment in original.segments):
        return blocked('Original speaker roles are unknown; no roles were inferred for the source.')
    if any(segment.start is not None for segment in original.segments):
        return blocked('Partial supplied original timings require explicit review; they were not replaced.')
    if not audio.duration_seconds or any(segment.start is None or segment.end is None or segment.start >= audio.duration_seconds for segment in reference.segments):
        return blocked('Complete, bounded reference timing is required for automatic evidence positions.')
    bounded = {index for index, segment in enumerate(reference.segments)
               if segment.end is not None and segment.end <= audio.duration_seconds + .25}
    starts = [segment.start for segment in reference.segments if segment.start is not None]
    if starts != sorted(starts):
        return blocked('Reference transcript order and audio positions disagree; no automatic reordering was performed.')
    left, right = _tokens(original), _tokens(reference)
    if not left or not right or max(len(left), len(right)) > 800:
        return blocked('Automatic full-call alignment supports 1–800 words per transcript; no partial denominator was used.')
    evidence, pairs = _speaker_map(original, reference, left, right, bounded)
    mapping = {item.speaker: item.role for item in evidence}
    if not evidence or set(mapping.values()) != {'caller', 'agent'}:
        return blocked('Unique phrases do not establish both reference speaker roles with sufficient support.')
    if any(segment.role != 'unknown' and mapping[segment.speaker] != segment.role for segment in reference.segments):
        return blocked('Inferred correspondence contradicts supplied reference roles; explicit roles were not overwritten.')
    result = STTReview(audio=audio, reference_source='deepgram', status='completed',
                       metric_kind='estimated_disagreement', edits=EditCounts())
    result.limitations.extend([
        'Whole mixed-call text disagreement with automatically inferred speaker roles; not caller-only accuracy or verified WER.',
        'Spelling, romanization and script variation can increase text disagreement without changing speech meaning.',
        'Audio positions are derived from Deepgram speech and neighbouring text anchors. Original Bolna utterance timestamps remain unavailable and unchanged.',
        'Unique four-word phrases support each role (at least 12 distinct reference words and 90% role dominance), with anchors in the first and final thirds of each source/reference role stream. These are support gates, not calibrated confidence or accuracy thresholds.',
    ])
    if len(bounded) != len(reference.segments):
        result.limitations.append('Provider end times exceed the recording in some segments. Those segments do not establish speaker identity or supply finding timestamps. Their words remain in the full text denominator; no provider timings were clamped.')
    matched_total = 0
    roles: list[KnownRole] = ['caller', 'agent']
    for role in roles:
        hyp = [token for token in left if original.segments[token.segment].role == role]
        ref = [token for token in right if mapping[reference.segments[token.segment].speaker] == role]
        source_positions = {index: position for position, index in enumerate(i for i, token in enumerate(left) if original.segments[token.segment].role == role)}
        reference_positions = {index: position for position, index in enumerate(i for i, token in enumerate(right) if mapping[reference.segments[token.segment].speaker] == role)}
        anchors = [(source_positions[i], reference_positions[j]) for speaker, source_role, i, j in pairs
                   if source_role == role and mapping[speaker] == role]
        if (not hyp or not ref or not anchors
                or min(i for i, _ in anchors) > len(hyp) / 3 or max(i for i, _ in anchors) < len(hyp) * 2 / 3
                or min(j for _, j in anchors) > len(ref) / 3 or max(j for _, j in anchors) < len(ref) * 2 / 3):
            return blocked('Unique anchors do not establish conversation-wide correspondence in both speaker roles; aggregate rate withheld.')
        path = _path(ref, hyp)
        matched = sum(i is not None and j is not None and ref[i].text == hyp[j].text for i, j in path)
        matched_total += matched
        counts = _counts(path, ref, hyp)
        assert result.edits is not None
        for name in ('substitutions', 'deletions', 'insertions', 'reference_words'):
            setattr(result.edits, name, getattr(result.edits, name) + getattr(counts, name))
        result.compared_groups += 1
        changed = [index for index, (i, j) in enumerate(path) if i is None or j is None or ref[i].text != hyp[j].text]
        groups: list[list[int]] = []
        for index in changed:
            if groups and index - groups[-1][-1] <= 3:
                groups[-1].append(index)
            else:
                groups.append([index])
        for group in groups:
            context = path[max(0, group[0] - 2):min(len(path), group[-1] + 3)]
            ref_indices = [i for i, _ in context if i is not None]
            hyp_indices = [j for _, j in context if j is not None]
            source_segments = {ref[i].segment for i in ref_indices}
            starts = [value for i in source_segments if (value := reference.segments[i].start) is not None]
            ends = [value for i in source_segments if (value := reference.segments[i].end) is not None]
            start, end = min(starts) if starts else None, max(ends) if ends else None
            if source_segments - bounded or start is not None and end is not None and end - start > 15:
                start, end = None, None
            finding = _finding(' '.join(hyp[j].text for j in hyp_indices), ' '.join(ref[i].text for i in ref_indices),
                               role, start, end, _counts(path[group[0]:group[-1] + 1], ref, hyp), False)
            finding.bolna_text = _quotes(hyp, hyp_indices, original)
            finding.reference_text = _quotes(ref, ref_indices, reference)
            finding.timing_basis = 'reference_anchors'
            finding.confidence_basis = 'Unverified reference and inferred role. Quotes preserve source turns; audio position comes from nearby reference speech, not an original Bolna timestamp.'
            result.findings.append(finding)
    result.alignment = AutomaticAlignment(speaker_roles=mapping, speaker_evidence=evidence,
                                          original_token_coverage=matched_total / len(left),
                                          reference_token_coverage=matched_total / len(right))
    assert result.edits is not None and result.edits.reference_words
    result.metric_value = (result.edits.substitutions + result.edits.deletions + result.edits.insertions) / result.edits.reference_words
    return result
