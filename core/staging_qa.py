"""Provider-free, explicitly opted-in Bolna QA collection for ephemeral staging."""

import asyncio
import hashlib
import os
from uuid import UUID
from typing import Any

import aiohttp
from fastapi import HTTPException

from api.schemas import WebhookEvent
from core.policy_store import PolicyStore
from core.reliability import evaluate_reliability
from core.speakers import attributed_transcript, parse_speaker_turns
from core.speech_diagnostics import bolna_speech_diagnostics
from core.staging import qa_agent_id
from core.stt_quality import STTReview
from core.stt_recording import inspect_recording, retrieve_qa_recording
from core.stt_sources import bolna_transcript
from storage.monitoring import MonitoringStore
from storage.stt_reviews import STTReviewStore


def validate_qa_event(event: WebhookEvent) -> None:
    if not qa_agent_id() or event.platform != 'bolna' or event.metadata.get('agent_id') != qa_agent_id():
        raise HTTPException(status_code=403, detail='Only the configured QA agent is accepted')
    try:
        UUID(event.call_id)
    except ValueError:
        raise HTTPException(status_code=422, detail='QA calls require a Bolna execution UUID')
    if not event.transcript or not event.transcript.strip():
        raise HTTPException(status_code=422, detail='Completed QA calls require the original Bolna transcript; no transcription provider will be called')


async def process_qa_call(event: WebhookEvent) -> dict:
    validate_qa_event(event)
    transcript = event.transcript or ''
    turns = parse_speaker_turns(transcript)
    policies = await PolicyStore().list_rules()
    reliability = evaluate_reliability(turns, policies)
    review = STTReview(status='blocked', issues=[
        'No independent reference transcript has been generated or human-verified.',
        'Bolna utterance timings and recording channel/role coverage have not been verified.',
    ])
    result: dict[str, Any] = {
        'run_id': event.call_id, 'platform': 'bolna', 'data_source': 'authorized_live_qa',
        'status': 'partial', 'agent_id': qa_agent_id(), 'transcript_source': 'bolna',
        'source_call': {'platform': 'bolna', 'call_id': event.call_id, 'agent_id': qa_agent_id()},
        'analysis': {'intent': 'Authorized Bolna QA test call'},
        'raw_transcript': transcript, 'attributed_transcript': attributed_transcript(turns),
        'transcript_speakers': turns,
        'transcript_meta': {'word_count': len(transcript.split()),
                            'duration_seconds': event.duration_ms / 1000 if event.duration_ms is not None else None},
        'reliability': reliability.model_dump(mode='json'),
        'policy_scope': 'Configured staging demo policies. Deterministic English patterns only; these are not verified agent instructions.',
        'speech_diagnostics': bolna_speech_diagnostics(event.raw).model_dump(mode='json'),
        'stt_source': bolna_transcript(transcript).model_dump(mode='json'),
        'stt_quality': review.model_dump(mode='json'),
        'report': {'quality_score': None, 'executive_summary':
                   'Authorized real QA call. Original Bolna transcript and provider diagnostics; deterministic staging policy checks only. '
                   'No LLM evaluator or independent transcription was called. STT is Not scored. Storage is ephemeral.',
                   'stt_quality': review.model_dump(mode='json')},
        'errors': [],
    }
    store = MonitoringStore()
    try:
        audio, content_type = await retrieve_qa_recording(event.call_id)
    except (ValueError, OSError, asyncio.TimeoutError, aiohttp.ClientError):
        result['errors'] = ['QA recording retrieval failed; webhook delivery must be retried.']
        await store.log_run(result)
        raise HTTPException(status_code=503, detail='Original QA transcript saved; recording retrieval failed. Retry delivery.', headers={'Retry-After': '30'})
    info = inspect_recording(audio)
    review.audio = info
    result['stt_quality'] = review.model_dump(mode='json')
    result['report']['stt_quality'] = result['stt_quality']
    artifacts = STTReviewStore()
    for key in os.getenv('VALID_API_KEYS', '').split(','):
        if key.strip():
            artifacts.save(hashlib.sha256(key.strip().encode()).hexdigest(), event.call_id,
                           audio=audio, content_type=content_type, audio_info=info.model_dump(mode='json'),
                           review=result['stt_quality'])
    result['status'] = 'completed'
    await store.log_run(result)
    return result
