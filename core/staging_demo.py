"""Reproducible synthetic staging data. Never calls a model or a voice platform."""

import base64
import copy
import hashlib
import json
import zlib
from pathlib import Path

from core.reliability import PolicyRule
from core.reliability_demo import demo_scenarios
from core.speakers import parse_speaker_turns
from core.staging import demo_enabled, public_demo_enabled, qa_agent_id, validate_demo_environment
from core.stt_quality import Segment, Transcript, compare_transcripts
from core.stt_recording import inspect_recording
from storage.monitoring import MonitoringStore
from storage.stt_reviews import STTReviewStore


def staging_scenarios() -> list[dict]:
    samples = copy.deepcopy(demo_scenarios())
    for sample, name in zip(samples, ['compliant', 'policy', 'escalation']):
        sample['run_id'] = 'demo-staging-' + name
        sample['analysis']['intent'] = 'Synthetic demo · ' + sample['analysis']['intent']
    template = samples[0]
    contradiction = copy.deepcopy(template)
    transcript = 'Customer: The total on my receipt is $100.\nAgent: Your receipt total is $900.'
    contradiction.update(
        run_id='demo-staging-hallucination', raw_transcript=transcript,
        attributed_transcript=transcript, transcript_speakers=parse_speaker_turns(transcript),
        reliability=None, evaluation_status='needs_review',
        synthetic_contradiction={'source_turn': 0, 'claim_turn': 1},
    )
    contradiction['analysis'].update(
        intent='Synthetic hallucination example · hand-labeled contradiction',
        hallucination_detected=True,
        hallucination_evidence='Synthetic fixture label: the agent states $900 after the supplied receipt total is $100. No live detector ran.',
    )
    contradiction['report'].update(
        executive_summary='Hand-labeled synthetic contradiction, not a live model verdict.', key_findings=[],
    )
    samples.append(contradiction)
    for name, intent in [('stt', 'Synthetic STT disagreement · signed amount'),
                         ('not-scored', 'Synthetic STT · timestamps unavailable')]:
        sample = copy.deepcopy(template)
        transcript = 'Caller: The balance is 100 dollars.'
        sample.update(run_id='demo-staging-' + name, raw_transcript=transcript,
                      attributed_transcript=transcript, transcript_speakers=parse_speaker_turns(transcript),
                      reliability=None)
        sample['analysis']['intent'] = intent
        sample['report'].update(executive_summary='Authored transcript fixture; no transcription provider ran.', key_findings=[])
        samples.append(sample)
    for sample in samples:
        sample['transcript_meta'].update(word_count=len(sample['raw_transcript'].split()),
                                         char_count=len(sample['raw_transcript']), duration_seconds=None)
        sample['staging_fixture'] = 'free_staging_v1'
        sample['report']['recommendations'] = ['Synthetic demo only. Inspect the supplied evidence; no production accuracy is measured.']
    return samples


def synthetic_stt_artifacts(timed: bool) -> dict:
    fixture = json.loads((Path(__file__).parent / 'data/staging_audio.json').read_text())
    audio = zlib.decompress(base64.b64decode(fixture['audio_zlib_base64']))
    info = inspect_recording(audio)
    if info.sha256 != fixture['sha256'] or not info.duration_seconds:
        raise ValueError('Synthetic audio fixture is invalid')
    info.scope = 'caller_only'
    info.scope_basis = 'One offline-generated synthetic voice. Caller role and coverage are authored fixture metadata.'
    timing = {'start': .6, 'end': info.duration_seconds} if timed else {}
    original = Transcript(source='synthetic', scope='caller_only', audio_sha256=info.sha256,
                          segments=[Segment(text='The balance is 100 dollars.', speaker='fixture-caller', role='caller', **timing)])
    reference = Transcript(source='synthetic', scope='caller_only', audio_sha256=info.sha256,
                           segments=[Segment(text='The balance is -100 dollars.', speaker='fixture-caller', role='caller', start=.6, end=info.duration_seconds)])
    review = compare_transcripts(original, reference, info)
    return {'audio': audio, 'content_type': 'audio/wav', 'audio_info': info.model_dump(),
            'reference': reference.model_dump(), 'annotations': original.model_dump(),
            'review': review.model_dump(mode='json'), 'original': original.model_dump()}


async def seed_staging_demo() -> dict:
    if not demo_enabled():
        raise ValueError('Synthetic demo mode is not enabled')
    keys = validate_demo_environment()
    store = MonitoringStore()
    reviews = STTReviewStore()
    if public_demo_enabled():
        offset = 0
        while True:
            page = await store.get_runs(limit=200, offset=offset)
            for item in page['runs']:
                saved = await store.get_run(item['run_id'])
                evaluation = (saved or {}).get('evaluation') or {}
                source = evaluation.get('source_call') or {}
                if (qa_agent_id() and evaluation.get('data_source') == 'authorized_live_qa'
                        and source.get('agent_id') == qa_agent_id()
                        and source.get('call_id') == item['run_id']
                        and source.get('platform') == 'bolna'):
                    continue
                if (not saved or not item['run_id'].startswith('demo-')
                        or (saved.get('evaluation') or {}).get('data_source') != 'synthetic_demo'):
                    raise ValueError('Public demo storage contains non-synthetic records; no records were deleted')
            if len(page['runs']) < 200:
                break
            offset += 200
    samples = staging_scenarios()
    for sample in samples:
        artifact = None
        if sample['run_id'] in ('demo-staging-stt', 'demo-staging-not-scored'):
            artifact = synthetic_stt_artifacts(sample['run_id'] == 'demo-staging-stt')
            sample['stt_source'] = artifact['original']
        existing = await store.get_run(sample['run_id'])
        if existing and (existing.get('evaluation') or {}).get('staging_fixture') != 'free_staging_v1':
            raise ValueError('A reserved staging fixture ID already contains other data; nothing was overwritten')
        if not existing:
            await store.log_run(sample)
        if artifact:
            values = {key: value for key, value in artifact.items() if key != 'original'}
            for key in keys:
                owner = hashlib.sha256(key.encode()).hexdigest()
                if not reviews.read(owner, sample['run_id']):
                    reviews.save(owner, sample['run_id'], **values)
    from core.policy_store import PolicyStore

    policies = PolicyStore()
    current = {rule.id for rule in await policies.list_rules()}
    for snapshot in samples[0]['reliability']['policy_snapshots']:
        rule = PolicyRule.model_validate(snapshot)
        if rule.id not in current:
            await policies.upsert_rule(rule)
    return {'seeded': len(samples), 'run_ids': [sample['run_id'] for sample in samples],
            'data_source': 'synthetic_demo', 'storage': 'ephemeral; synthetic fixtures can be restored'}
