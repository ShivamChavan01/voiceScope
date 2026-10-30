"""Authenticated, explicitly requested post-call STT reviews. No background uploads."""

import hashlib
import copy

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
    run = await get_monitoring_store().get_run(run_id)
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
    if body.consent_to_deepgram is False:
        raise HTTPException(status_code=422, detail='Deepgram transcription was explicitly declined')
    try:
        return await create_reference(run, owner_for(request), STTReviewStore())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


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
    return Response(content=stored['audio'], media_type=stored.get('content_type') or 'audio/wav', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
