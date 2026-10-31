import pytest
from pydantic import ValidationError

from core.stt_quality import AudioInfo, Segment, Transcript, compare_transcripts, edit_counts, meaning_changes

HASH = 'a' * 64


def document(text='I want a refund', source='bolna', verified=False, role='caller', start=0, end=3, scope='caller_only'):
    return Transcript(source=source, scope=scope, audio_sha256=HASH if source != 'bolna' else None,
        human_verified=verified, verified_by='Test reviewer' if verified else None,
        segments=[Segment(text=text, speaker='one', role=role, start=start, end=end)])


def audio(scope='caller_only'):
    return AudioInfo(available=True, sha256=HASH, scope=scope, duration_seconds=20)


@pytest.mark.parametrize('reference,hypothesis,expected', [
    ('one two three', 'one four three', (1, 0, 0, 3)),
    ('one two three', 'one three', (0, 1, 0, 3)),
    ('one three', 'one two three', (0, 0, 1, 2)),
    ('', 'one two', (0, 0, 2, 0)), ('one two', '', (0, 2, 0, 2)),
    ('Hello, WORLD!', 'hello world', (0, 0, 0, 2)),
])
def test_edit_counts_known_edits(reference, hypothesis, expected):
    result = edit_counts(reference, hypothesis)
    assert (result.substitutions, result.deletions, result.insertions, result.reference_words) == expected


def test_ground_truth_wer_and_auto_disagreement_are_distinct():
    original = document('I want refund')
    human = compare_transcripts(original, document('I want a refund', 'human', True), audio())
    assert human.metric_kind == 'wer'
    assert human.metric_value == 0.25
    assert human.findings[0].status == 'confirmed_error'
    automatic = compare_transcripts(original, document('I want a refund', 'deepgram'), audio())
    assert automatic.metric_kind == 'estimated_disagreement'
    assert automatic.metric_value == 0.25
    assert automatic.findings[0].status == 'needs_review'
    assert automatic.findings[0].confidence == 'low'


def test_rate_can_exceed_one_without_clamping():
    result = compare_transcripts(document('one two three four'), document('one', 'human', True), audio())
    assert result.metric_value == 3


@pytest.mark.parametrize('reference,hypothesis,category', [
    ('I do not want a refund', 'I do want a refund', 'negation'),
    ('Refund is $100', 'Refund is $1000', 'amount'),
    ('Appointment is Monday', 'Appointment is Tuesday', 'date'),
    ('My name is Alice', 'My name is Alex', 'name'),
    ('My address is 12 Main Street', 'My address is 21 Main Street', 'address'),
    ('Please cancel the booking', 'Please renew the booking', 'user_intent'),
])
def test_meaning_change_categories(reference, hypothesis, category):
    assert category in meaning_changes(reference, hypothesis)


def test_mixed_reference_is_filtered_by_confirmed_role_for_caller_only_bolna():
    reference = document('I want a refund', 'deepgram', scope='mixed')
    reference.segments.append(Segment(text='How can I help', role='agent', speaker='two', start=4, end=6))
    result = compare_transcripts(document(), reference, audio('mixed'))
    assert result.metric_value == 0
    assert result.edits.reference_words == 4


def test_mixed_and_caller_only_never_compare_unsegmented():
    result = compare_transcripts(document(scope='mixed'), document(source='deepgram'), audio('mixed'))
    assert result.status == 'blocked'
    assert result.metric_value is None
    unknown = compare_transcripts(document(), document(source='deepgram', role='unknown', scope='mixed'), audio('mixed'))
    assert unknown.status == 'blocked'


@pytest.mark.parametrize('problem', ['audio', 'scope', 'hash', 'time', 'duration'])
def test_missing_evidence_withholds_scores(problem):
    original, reference, recording = document(), document('I do not want a refund', 'human', True), audio()
    if problem == 'audio':
        recording.available = False
    if problem == 'scope':
        recording.scope = 'unknown'
    if problem == 'hash':
        reference.audio_sha256 = 'b' * 64
    if problem == 'time':
        original.segments[0].start = original.segments[0].end = None
    if problem == 'duration':
        reference.segments[0].end = 40
    result = compare_transcripts(original, reference, recording)
    assert result.metric_value is None
    assert result.issues
    assert all(finding.status == 'needs_review' for finding in result.findings)


def test_time_and_role_alignment_not_list_position():
    original = document('hello', scope='mixed')
    original.segments.append(Segment(text='goodbye', role='agent', speaker='agent', start=5, end=8))
    reference = document('goodbye', source='deepgram', role='agent', start=5, end=8, scope='mixed')
    reference.segments.append(Segment(text='hello', role='caller', speaker='caller', start=0, end=3))
    result = compare_transcripts(original, reference, audio('mixed'))
    assert result.metric_value == 0
    assert result.compared_groups == 2


def test_unmatched_intervals_are_not_dropped():
    result = compare_transcripts(document('one', start=0, end=2), document('two', 'human', True, start=5, end=8), audio())
    assert result.edits.insertions == 1
    assert result.edits.deletions == 1
    assert result.metric_value == 2
    assert [finding.start for finding in result.findings] == [0, 5]


def test_models_cannot_claim_human_verification_without_attestation():
    with pytest.raises(ValidationError):
        Transcript(source='deepgram', human_verified=True, verified_by='Person', audio_sha256=HASH)
    with pytest.raises(ValidationError):
        Transcript(source='human', human_verified=True, audio_sha256=HASH)


@pytest.mark.parametrize('start,end', [(0, None), (2, 1), (float('nan'), 3), (-1, 1)])
def test_invalid_timing_rejected(start, end):
    with pytest.raises(ValidationError):
        Segment(text='hello', speaker='one', start=start, end=end)


def test_long_intervals_do_not_produce_partial_global_scores():
    result = compare_transcripts(document('word ' * 801), document(source='deepgram'), audio())
    assert result.status == 'partial'
    assert result.metric_value is None


def test_empty_reference_is_not_zero_error():
    result = compare_transcripts(document(), Transcript(source='deepgram', scope='caller_only', audio_sha256=HASH), audio())
    assert result.metric_value is None
    assert result.status == 'blocked'


def test_zero_token_reference_withholds_rate_and_marks_partial():
    result = compare_transcripts(document('hello'), document('...', 'human', True), audio())
    assert result.status == 'partial'
    assert result.metric_kind is None
    assert result.metric_value is None
    assert result.edits.reference_words == 0


@pytest.mark.parametrize('human', [False, True])
@pytest.mark.parametrize('amount', ['-100', '−100', '-$100', '$-100', 'negative 100', '-100.50'])
def test_signed_amount_disagreement_is_preserved(amount, human):
    original = document('The balance is 100 dollars')
    reference = document(f'The balance is {amount} dollars', 'human' if human else 'deepgram', human)
    result = compare_transcripts(original, reference, audio())
    assert result.metric_value > 0
    assert 'amount' in result.findings[0].category
    assert result.findings[0].status == ('confirmed_error' if human else 'needs_review')


def test_hyphens_in_dates_are_not_negative_signs():
    from core.stt_quality import words
    assert words('Date 2026-10-31') == ['date', '2026', '10', '31']
