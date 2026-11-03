import copy

import pytest

from core.stt_quality import AudioInfo, Segment, Transcript, words

HASH = 'a' * 64


def documents(change=None):
    turns = [
        ('caller', 'I would like to check my booking for Monday morning.'),
        ('agent', 'I can check the booking details in our account system.'),
        ('caller', 'The address on my account is 12 Main Street please.'),
        ('agent', 'Let me read the address back so you can confirm.'),
    ]
    original = Transcript(source='bolna', scope='mixed', segments=[
        Segment(text=text, speaker=role, role=role) for role, text in turns])
    reference = Transcript(source='deepgram', audio_sha256=HASH, segments=[
        Segment(text=text.replace('Monday', change) if change else text,
                speaker='dg_1' if role == 'caller' else 'dg_0', start=i * 6 + .2, end=i * 6 + 5)
        for i, (role, text) in enumerate(turns)])
    recording = AudioInfo(available=True, sha256=HASH, duration_seconds=30, channels=2)
    return original, reference, recording


def test_unique_anchors_support_estimated_disagreement_without_mutating_sources():
    from core.stt_alignment import compare_with_automatic_alignment
    original, reference, audio = documents('Tuesday')
    before = copy.deepcopy((original, reference, audio))
    result = compare_with_automatic_alignment(original, reference, audio)
    assert result.metric_kind == 'estimated_disagreement'
    assert result.edits.substitutions == 1
    assert result.edits.deletions == result.edits.insertions == 0
    assert result.metric_value == pytest.approx(1 / sum(len(words(s.text)) for s in reference.segments))
    assert result.alignment.speaker_roles == {'dg_0': 'agent', 'dg_1': 'caller'}
    assert result.alignment.method == 'unique_text_anchors_v1'
    assert result.findings[0].category == ['date']
    assert result.findings[0].status == 'needs_review'
    assert result.findings[0].confidence == 'low'
    assert result.findings[0].timing_basis == 'reference_anchors'
    assert 'Monday' in result.findings[0].bolna_text
    assert 'Tuesday' in result.findings[0].reference_text
    assert result.reference_human_verified is False
    assert (original, reference, audio) == before


@pytest.mark.parametrize('problem', ['audio', 'hash', 'original_hash', 'caller_only', 'unknown_original',
                                  'no_timing', 'duration', 'one_voice', 'weak_text', 'partial_timing',
                                  'reference_caller_only', 'nonmonotonic', 'overlimit'])
def test_missing_or_ambiguous_evidence_stays_unscored(problem):
    from core.stt_alignment import compare_with_automatic_alignment
    original, reference, audio = documents()
    if problem == 'audio':
        audio.available = False
    elif problem == 'hash':
        reference.audio_sha256 = 'b' * 64
    elif problem == 'original_hash':
        original.audio_sha256 = 'b' * 64
    elif problem == 'caller_only':
        original.segments = [s for s in original.segments if s.role == 'caller']
        original.scope = 'caller_only'
    elif problem == 'unknown_original':
        original.segments[0].role = 'unknown'
    elif problem == 'no_timing':
        reference.segments[0].start = reference.segments[0].end = None
    elif problem == 'duration':
        reference.segments[-1].end = 100
    elif problem == 'one_voice':
        for segment in reference.segments:
            segment.speaker = 'dg_0'
    elif problem == 'weak_text':
        for segment in reference.segments:
            segment.text = 'Unrelated words provide no trustworthy source match.'
    elif problem == 'partial_timing':
        original.segments[0].start, original.segments[0].end = 0, 5
    elif problem == 'reference_caller_only':
        reference.scope = 'caller_only'
    elif problem == 'nonmonotonic':
        reference.segments.reverse()
    elif problem == 'overlimit':
        original.segments[0].text = 'word ' * 801
    result = compare_with_automatic_alignment(original, reference, audio)
    assert result.metric_value is None
    assert result.issues
    assert not any(f.status == 'confirmed_error' for f in result.findings)


def test_repeated_phrases_cannot_create_a_speaker_identity():
    from core.stt_alignment import compare_with_automatic_alignment
    original, reference, audio = documents()
    for segment in original.segments + reference.segments:
        segment.text = 'Please tell me what happens next.'
    assert compare_with_automatic_alignment(original, reference, audio).metric_value is None


def test_alignment_is_deterministic_and_speaker_numbers_have_no_role_meaning():
    from core.stt_alignment import compare_with_automatic_alignment
    original, reference, audio = documents()
    for segment in reference.segments:
        segment.speaker = 'voice-A' if segment.speaker == 'dg_0' else 'voice-B'
    result = compare_with_automatic_alignment(original, reference, audio)
    assert result.metric_value == 0
    assert result.alignment.speaker_roles == {'voice-A': 'agent', 'voice-B': 'caller'}
    assert result == compare_with_automatic_alignment(original, reference, audio)


def test_unicode_marks_and_signed_numbers_are_preserved():
    assert words('मुझे मेरा रिफंड नहीं चाहिए।') == ['मुझे', 'मेरा', 'रिफंड', 'नहीं', 'चाहिए']
    assert words('100 −100 ₹-100') == ['100', '-100', '₹-100']


def test_alignment_cannot_turn_a_human_reference_without_timings_into_wer():
    from core.stt_alignment import compare_with_automatic_alignment
    original, reference, audio = documents()
    reference.source = 'human'
    reference.human_verified = True
    reference.verified_by = 'Synthetic reviewer'
    assert compare_with_automatic_alignment(original, reference, audio).metric_value is None


def test_distributed_anchors_do_not_hide_high_disagreement_calls():
    from core.stt_alignment import compare_with_automatic_alignment
    original = Transcript(source='bolna', scope='mixed', segments=[
        Segment(text=' '.join(f'{role}word{i}' for i in range(60)), speaker=role, role=role)
        for role in ('caller', 'agent')])
    reference = Transcript(source='deepgram', audio_sha256=HASH, segments=[
        Segment(text=' '.join(f'changed{role}{i}' if 20 <= i < 40 else f'{role}word{i}' for i in range(60)),
                speaker=role + '-voice', start=index * 10, end=index * 10 + 9)
        for index, role in enumerate(('caller', 'agent'))])
    result = compare_with_automatic_alignment(original, reference, AudioInfo(available=True, sha256=HASH, duration_seconds=25))
    assert result.metric_value == pytest.approx(40 / 120)
    assert result.edits.substitutions == 40


def test_single_local_anchor_does_not_establish_full_call_coverage():
    from core.stt_alignment import compare_with_automatic_alignment
    original, reference, audio = documents()
    for segment in original.segments:
        segment.text += ' ' + ' '.join(f'sourceonly{i}' for i in range(80))
    assert compare_with_automatic_alignment(original, reference, audio).metric_value is None


def test_edit_backtrace_matches_known_counts_for_reproducible_cases():
    import random
    from core.stt_alignment import Token, _counts, _path
    from core.stt_quality import edit_counts
    rng = random.Random(86102)
    for _ in range(200):
        ref = [rng.choice(['one', 'two', 'three', '-100', '100']) for _ in range(rng.randrange(12))]
        hyp = [rng.choice(['one', 'two', 'three', '-100', '100']) for _ in range(rng.randrange(12))]
        left, right = [Token(t, 0) for t in ref], [Token(t, 0) for t in hyp]
        assert _counts(_path(left, right), left, right) == edit_counts(' '.join(ref), ' '.join(hyp)), 'seed=86102'


def test_provider_end_overrun_is_not_clamped_or_dropped_from_denominator():
    from core.stt_alignment import compare_with_automatic_alignment
    original, reference, audio = documents()
    original.segments.append(Segment(text='Goodbye.', speaker='agent', role='agent'))
    reference.segments.append(Segment(text='Goodbye.', speaker='dg_0', start=29, end=31))
    result = compare_with_automatic_alignment(original, reference, audio)
    assert result.metric_value == 0
    assert result.edits.reference_words == sum(len(words(s.text)) for s in reference.segments)
    assert reference.segments[-1].end == 31
    assert any('no provider timings were clamped' in x for x in result.limitations)


def test_restore_reference_binds_bytes_and_persists_alignment_without_a_provider(tmp_path, monkeypatch):
    import hashlib
    from core.stt_service import restore_reference
    from storage.stt_reviews import STTReviewStore
    from stt_providers.registry import STTRegistry
    original, reference, audio = documents('Tuesday')
    raw = b'synthetic original recording bytes'
    reference.audio_sha256 = audio.sha256 = hashlib.sha256(raw).hexdigest()
    run = {'run_id': 'synthetic-test', 'evaluation': {'stt_source': original.model_dump()}}
    store = STTReviewStore(tmp_path)
    store.save('owner', run['run_id'], audio=raw, audio_info=audio.model_dump())
    monkeypatch.setattr(STTRegistry, 'get', lambda *args: pytest.fail('Cached restoration called a paid provider'))
    result = restore_reference(run, 'owner', reference, store)
    assert result['review']['metric_kind'] == 'estimated_disagreement'
    assert result['review']['alignment']['speaker_roles']['dg_0'] == 'agent'
    assert store.read('owner', run['run_id'])['review'] == result['review']
    store.save('owner', run['run_id'], audio=b'changed recording')
    with pytest.raises(ValueError, match='audio bytes'):
        restore_reference(run, 'owner', reference, store)


def test_inferred_roles_do_not_override_explicit_reference_labels():
    from core.stt_alignment import compare_with_automatic_alignment
    original, reference, audio = documents()
    reference.segments[0].role = 'agent'
    assert compare_with_automatic_alignment(original, reference, audio).metric_value is None
    assert reference.segments[0].role == 'agent'


def test_supplied_timed_human_comparison_rejects_an_original_hash_mismatch():
    from core.stt_quality import compare_transcripts
    original, reference, audio = documents()
    for left, right in zip(original.segments, reference.segments):
        left.start, left.end = right.start, right.end
        right.role = left.role
    reference.scope = audio.scope = 'mixed'
    reference.source, reference.human_verified, reference.verified_by = 'human', True, 'Synthetic reviewer'
    original.audio_sha256 = 'b' * 64
    assert compare_transcripts(original, reference, audio).metric_value is None
