from unittest.mock import AsyncMock, patch

import pytest

from agents.speaker_agent import SpeakerAgent
from core.context import PipelineContext
from core.speakers import attributed_transcript, parse_speaker_turns


def test_bolna_roles_preserved_when_customer_speaks_first():
    turns = parse_speaker_turns('user: I need a refund.\nassistant: I can help.\nuser: Thank you.')
    assert [turn['role'] for turn in turns] == ['customer', 'agent', 'customer']
    assert turns[0]['speaker'] == turns[2]['speaker']
    assert all(turn['role_source'] == 'transcript_label' for turn in turns)


@pytest.mark.parametrize('text', ['', 'Hello without labels', 'Intro text\nAgent: Hello'])
def test_unlabelled_text_is_not_guessed(text):
    assert parse_speaker_turns(text) == []


def test_numeric_speaker_ids_are_not_roles_and_multiline_text_survives():
    turns = parse_speaker_turns('Caller 1: Hello\ncontinuation\nCaller 2: Hi')
    assert [turn['role'] for turn in turns] == ['unknown', 'unknown']
    assert turns[0]['text'] == 'Hello\ncontinuation'


def test_attribution_text_marks_inference_and_unknown_roles():
    text = attributed_transcript([
        {'speaker': 0, 'role': 'customer', 'role_source': 'model_inference', 'text': 'Hello'},
        {'speaker': 1, 'role': 'unknown', 'text': 'Hi'},
    ])
    assert text == 'Customer (inferred): Hello\nSpeaker 1 (role unknown): Hi'


async def test_explicit_roles_do_not_require_model_call():
    with patch('agents.speaker_agent.ProviderRegistry') as registry:
        registry.call = AsyncMock()
        ctx = PipelineContext(transcript_speakers=parse_speaker_turns('assistant: Hello\nuser: Hi'))
        await SpeakerAgent().run(ctx)
        registry.call.assert_not_awaited()
    assert [turn['label'] for turn in ctx.transcript_speakers] == ['Agent', 'Customer']


async def test_explicit_role_survives_failed_inference_for_another_speaker():
    turns = parse_speaker_turns('assistant: How can I help?\nSpeaker 2: Hello')
    with patch('agents.speaker_agent.ProviderRegistry') as registry:
        registry.call = AsyncMock(side_effect=RuntimeError('unavailable'))
        ctx = PipelineContext(transcript_speakers=turns)
        await SpeakerAgent().run(ctx)
    assert turns[0]['role'] == 'agent'
    assert turns[0]['role_source'] == 'transcript_label'
    assert turns[1]['role'] == 'unknown'


def test_deepgram_word_diarization_survives_missing_paragraphs():
    from stt_providers.deepgram_provider import speaker_segments

    turns = speaker_segments({'words': [
        {'speaker': 8, 'punctuated_word': 'Help,'},
        {'speaker': 8, 'word': 'please'},
        {'speaker': 3, 'punctuated_word': 'Certainly.'},
    ]})
    assert turns == [{'speaker': 8, 'text': 'Help, please'}, {'speaker': 3, 'text': 'Certainly.'}]


def test_deepgram_paragraph_speakers_and_words_are_preserved():
    from stt_providers.deepgram_provider import speaker_segments

    turns = speaker_segments({'paragraphs': {'paragraphs': [
        {'speaker': 1, 'sentences': [{'text': 'Hello.'}, {'text': 'Can you help?'}]},
        {'speaker': 0, 'sentences': [{'text': 'Yes.'}]},
    ]}})
    assert turns == [{'speaker': 1, 'text': 'Hello. Can you help?'}, {'speaker': 0, 'text': 'Yes.'}]


@pytest.mark.parametrize('alternative', [
    {'transcript': 'Mixed voices, no speaker labels.'},
    {'transcript': 'Mixed voices, no speaker labels.', 'words': [{'word': 'Mixed'}]},
])
async def test_missing_diarization_is_not_inferred_as_one_person(alternative):
    from stt_providers.deepgram_provider import speaker_segments

    with patch('agents.speaker_agent.ProviderRegistry') as registry:
        registry.call = AsyncMock()
        ctx = PipelineContext(transcript_speakers=speaker_segments(alternative))
        await SpeakerAgent().run(ctx)
        registry.call.assert_not_awaited()
    assert ctx.transcript_speakers[0]['role'] == 'unknown'
    assert ctx.errors


def test_empty_stt_does_not_invent_speakers():
    from stt_providers.deepgram_provider import speaker_segments

    assert speaker_segments({}) == []


def test_unknown_label_does_not_merge_into_preceding_agent_turn():
    turns = parse_speaker_turns('Agent: I can help.\nSupervisor: I need more context.')
    assert len(turns) == 2
    assert turns[0]['text'] == 'I can help.'
    assert turns[1]['role'] == 'unknown'
    assert turns[0]['speaker'] != turns[1]['speaker']


def test_inferred_role_turns_still_split_for_long_call_analysis():
    from agents.analysis_agent import _chunk_turns, _split_by_speaker_turns

    turns = [{'speaker': i % 2, 'role': 'agent' if i % 2 == 0 else 'customer',
              'role_source': 'model_inference', 'text': 'word ' * 150} for i in range(40)]
    text = attributed_transcript(turns)
    split = _split_by_speaker_turns(text)
    assert len(split) == 40
    assert all(len(chunk.split()) <= 1000 for chunk in _chunk_turns(split, 1000))


async def test_plain_transcript_without_speaker_structure_requires_review():
    from core.pipeline import VoiceScopePipeline

    with patch('core.pipeline.ChromaStore'), patch('core.pipeline.KnowledgeBase'), \
         patch('core.pipeline.AnalysisAgent'), patch('core.pipeline.ReportAgent'), \
         patch('core.pipeline.SpeakerAgent') as factory, \
         patch('agents.speaker_agent.ProviderRegistry') as registry:
        factory.return_value = SpeakerAgent()
        registry.call = AsyncMock()
        pipeline = VoiceScopePipeline()
        ctx = await pipeline.attribute_speakers(PipelineContext(raw_transcript='I need a refund. I have processed it.'))
        registry.call.assert_not_awaited()
    assert ctx.transcript_speakers[0]['role'] == 'unknown'
    assert 'role unknown' in ctx.attributed_transcript
    assert ctx.errors
