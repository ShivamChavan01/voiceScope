"""Authenticated, explicitly requested post-call STT reviews. No background uploads."""

import hashlib
import copy
import re

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from core.stt_service import CompareRequest, create_reference, evaluate_run, retrieve_recording, state_for_run
from storage.stt_reviews import STTReviewStore

router = APIRouter()


def owner_for(request: Request) -> str:
    key = request.headers.get('X-API-Key')
    if not key:
        raise HTTPException(status_code=401, detail='API key required')
    return hashlib.sha256(key.encode()).hexdigest()


async def load_run(run_id: str) -> dict:
    from api.routes import get_monitoring_store
    run: dict | None = await get_monitoring_store().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Run not found')
    return run


def attach_stt_report(run: dict, request: Request) -> dict:
    if request.headers.get('X-STT-Review') != '1':
        return run
    stored = STTReviewStore().read(owner_for(request), run['run_id'])
    if stored and stored.get('review'):
        review = state_for_run(run, stored)['review']
        run = copy.deepcopy(run)
        evaluation = run.get('evaluation') or {}
        evaluation['stt_quality'] = review
        if evaluation.get('report') is None:
            evaluation['report'] = {}
        evaluation['report']['stt_quality'] = {
            'comparison_version': review.get('comparison_version'),
            'status': review['status'], 'metric_kind': review['metric_kind'],
            'metric_value': review['metric_value'], 'issues': review['issues'],
            'reference_source': review['reference_source'],
            'reference_human_verified': review['reference_human_verified'],
            'verified_by': review['verified_by'], 'edits': review['edits'],
            'limitations': review['limitations'],
            'evidence': review['findings'],
        }
        run['evaluation'] = evaluation
    return run


@router.get('/runs/{run_id}/stt-review')
async def get_review(run_id: str, request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    run = await load_run(run_id)
    return state_for_run(run, STTReviewStore().read(owner_for(request), run_id))


@router.post('/runs/{run_id}/stt-review/recording')
async def fetch_recording(run_id: str, request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    run = await load_run(run_id)
    return await retrieve_recording(run, owner_for(request), STTReviewStore())


class ReferenceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: str = Field(default='deepgram', pattern='^deepgram$')
    # Preserve an explicit opt-out from older clients without requiring repeated consent.
    consent_to_deepgram: bool | None = Field(default=None, strict=True)


@router.post('/runs/{run_id}/stt-review/reference')
async def generate_reference(run_id: str, body: ReferenceRequest, request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    run = await load_run(run_id)
    from core.staging import qa_agent_id, qa_deepgram_enabled
    if qa_agent_id():
        evaluation = run.get('evaluation') or {}
        if (not qa_deepgram_enabled() or evaluation.get('data_source') != 'authorized_live_qa'
                or (evaluation.get('source_call') or {}).get('agent_id') != qa_agent_id()):
            raise HTTPException(status_code=403, detail='Independent QA transcription is restricted to the configured test agent')
    if body.consent_to_deepgram is False:
        raise HTTPException(status_code=422, detail='Deepgram transcription was explicitly declined')
    try:
        return await create_reference(run, owner_for(request), STTReviewStore())
    except ValueError:
        raise HTTPException(status_code=422, detail='Reference preparation is unavailable. Check provider configuration and the saved original transcript.')


@router.post('/runs/{run_id}/stt-review')
async def run_review(run_id: str, body: CompareRequest, request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    run = await load_run(run_id)
    try:
        return evaluate_run(run, owner_for(request), body, STTReviewStore())
    except ValueError:
        raise HTTPException(status_code=422, detail='Invalid transcript annotation or reference. Preserve original words and verify the recording hash.')


@router.get('/runs/{run_id}/stt-review/audio')
async def review_audio(run_id: str, request: Request):
    await load_run(run_id)
    stored = STTReviewStore().read(owner_for(request), run_id)
    if not stored or not stored.get('audio'):
        raise HTTPException(status_code=404, detail='Private recording is unavailable or expired')
    audio = stored['audio']
    size = len(audio)
    headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Accept-Ranges': 'bytes'}
    value = request.headers.get('range')
    status = 200
    if value and not request.headers.get('if-range'):
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', value) if len(value) <= 128 else None
        start, end = 0, size - 1
        valid = bool(match and any(match.groups()) and size)
        if valid and match:
            first, last = match.groups()
            if first:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            else:
                suffix = int(last)
                valid = suffix > 0
                start = max(0, size - suffix)
            valid = valid and start <= end and start < size
        if not valid:
            return Response(status_code=416, headers={**headers, 'Content-Range': f'bytes */{size}'})
        headers['Content-Range'] = f'bytes {start}-{end}/{size}'
        audio = audio[start:end + 1]
        status = 206
    return Response(content=audio, status_code=status, media_type=stored.get('content_type') or 'audio/wav', headers=headers)
