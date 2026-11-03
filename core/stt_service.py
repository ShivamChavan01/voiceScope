"""Opt-in post-call reference generation and review orchestration."""

import asyncio
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.stt_quality import COMPARISON_VERSION, AudioInfo, Scope, STTReview, Transcript
from core.stt_alignment import compare_with_automatic_alignment
from core.stt_recording import inspect_recording, retrieve_bolna_recording
from core.stt_sources import bolna_transcript, deepgram_reference, validate_bolna_annotations
from storage.stt_reviews import STTReviewStore
from stt_providers.registry import STTRegistry


_REFERENCE_TASKS: dict[tuple, asyncio.Task] = {}


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    recording_scope: Scope = 'unknown'
    scope_confirmed: bool = Field(default=False, strict=True)
    target: Literal['caller_only', 'mixed'] = 'caller_only'
    speaker_roles: dict[str, Literal['caller', 'agent']] = Field(default_factory=dict, max_length=100)
    speaker_mapping_confirmed: bool = Field(default=False, strict=True)
    bolna_annotations: Transcript | None = None
    human_reference: Transcript | None = None

    @model_validator(mode='after')
    def attestations(self):
        if self.speaker_roles and not self.speaker_mapping_confirmed:
            raise ValueError('Confirm speaker mapping after listening to the original audio')
        if self.human_reference and self.human_reference.source != 'human':
            raise ValueError('Human reference must declare a verified human source')
        return self


def original_transcript(run: dict) -> Transcript:
    evaluation = run.get('evaluation') or {}
    saved = evaluation.get('stt_source')
    if saved:
        return Transcript.model_validate(saved)
    source = evaluation.get('source_call') or {}
    if source.get('platform') != 'bolna' or evaluation.get('transcript_source') != 'bolna':
        return Transcript(source='bolna')
    return bolna_transcript(evaluation.get('raw_transcript') or '')


def state_for_run(run: dict, stored: dict | None) -> dict:
    import os
    from core.staging import demo_enabled, qa_deepgram_enabled
    stored = stored or {}
    original = original_transcript(run)
    review = stored.get('review')
    if (review and review.get('comparison_version') != COMPARISON_VERSION
            and (review.get('metric_value') is not None or review.get('findings'))):
        # Never keep displaying a cached rate computed with retired token rules.
        # Reading does not invoke a provider, extend expiry, or invent alignment.
        review = STTReview(
            audio=AudioInfo.model_validate(stored.get('audio_info') or {}),
            reference_source=review.get('reference_source'),
            reference_human_verified=review.get('reference_human_verified', False),
            verified_by=review.get('verified_by'),
            issues=['This saved comparison uses earlier scoring rules. Compare again to refresh findings using the retained reference and recording.'],
        ).model_dump(mode='json')
    if stored.get('annotations'):
        try:
            annotated = Transcript.model_validate(stored['annotations'])
            if annotated.audio_sha256 != (stored.get('audio_info') or {}).get('sha256'):
                raise ValueError('Recording changed')
            original = validate_bolna_annotations(original, annotated)
        except ValueError:
            # Evidence from a different source must not retain a score or confirmed findings.
            review = STTReview(audio=AudioInfo.model_validate(stored.get('audio_info') or {}),
                               issues=['Saved timing annotations no longer match the original transcript or recording. Review and annotate the current source before scoring.']).model_dump(mode='json')
    return {
        'review': review,
        'reference': stored.get('reference'),
        'bolna': original.model_dump(mode='json'),
        'audio': stored.get('audio_info') or AudioInfo().model_dump(),
        'provider': {'name': 'deepgram', 'configured': bool(os.getenv('DEEPGRAM_API_KEY')) and (not demo_enabled() or qa_deepgram_enabled()), 'requires_consent': False},
    }


async def retrieve_recording(run: dict, owner: str, store: STTReviewStore) -> dict:
    """Retrieve from Bolna only; never invoke a transcription provider."""
    run_id = run['run_id']
    stored = store.read(owner, run_id) or {}
    if stored.get('audio'):
        return state_for_run(run, stored)
    source = (run.get('evaluation') or {}).get('source_call') or {}
    if source.get('platform') != 'bolna' or not source.get('call_id'):
        review = STTReview(issues=['No completed Bolna recording reference is stored for this run.'])
    else:
        try:
            data, content_type = await retrieve_bolna_recording(source['call_id'])
            info = inspect_recording(data)
            store.save(owner, run_id, audio=data, content_type=content_type, audio_info=info.model_dump(), review=STTReview(audio=info, issues=['Original recording is available. Supply and align a separate reference before scoring.']).model_dump(mode='json'))
            return state_for_run(run, store.read(owner, run_id))
        except Exception:
            review = STTReview(status='failed', issues=['Original recording retrieval failed. No audio was sent to a transcription provider.'])
    store.save(owner, run_id, review=review.model_dump(mode='json'))
    return state_for_run(run, store.read(owner, run_id))


async def create_reference(run: dict, owner: str, store: STTReviewStore) -> dict:
    """The authenticated review action uses the workspace-authorized Deepgram provider.

    Concurrent requests in this worker share one submission; successful references
    persist across reloads. No provider runs from a GET or live-call callback.
    """
    key = (id(asyncio.get_running_loop()), str(store.path), owner, run['run_id'])
    task = _REFERENCE_TASKS.get(key)
    if task is None:
        task = asyncio.create_task(_create_reference(run, owner, store))
        _REFERENCE_TASKS[key] = task
        task.add_done_callback(lambda finished: _REFERENCE_TASKS.pop(key, None))
    return await asyncio.shield(task)


async def _create_reference(run: dict, owner: str, store: STTReviewStore) -> dict:
    import os
    run_id = run['run_id']
    stored = store.read(owner, run_id) or {}
    if stored.get('reference'):
        if (stored.get('review') or {}).get('comparison_version') != COMPARISON_VERSION:
            review = _compare_saved(run, stored, Transcript.model_validate(stored['reference']))
            store.save(owner, run_id, review=review.model_dump(mode='json'))
        return state_for_run(run, store.read(owner, run_id))
    if not os.getenv('DEEPGRAM_API_KEY'):
        raise ValueError('Deepgram credentials are not configured')
    source = (run.get('evaluation') or {}).get('source_call') or {}
    if source.get('platform') != 'bolna' or not source.get('call_id'):
        review = STTReview(issues=['No completed Bolna recording reference is stored for this run.'])
        store.save(owner, run_id, review=review.model_dump(mode='json'))
        return state_for_run(run, store.read(owner, run_id))
    if not original_transcript(run).segments:
        review = STTReview(issues=['Original Bolna transcript is absent. No recording was sent to the provider.'])
        store.save(owner, run_id, review=review.model_dump(mode='json'))
        return state_for_run(run, store.read(owner, run_id))
    try:
        if stored.get('audio'):
            data = stored['audio']
            info = AudioInfo.model_validate(stored['audio_info'])
        else:
            data, content_type = await retrieve_bolna_recording(source['call_id'])
            info = inspect_recording(data)
            store.save(owner, run_id, audio=data, content_type=content_type, audio_info=info.model_dump())
        if not info.sha256:
            raise ValueError('Original recording hash is unavailable')
        result = await asyncio.wait_for(STTRegistry.get('deepgram').transcribe(data, 'completed-call.wav'), timeout=75)
        reference = deepgram_reference(result, info.sha256)
        if not reference.segments:
            raise ValueError('Provider produced no reference speech')
        review = _compare_saved(run, store.read(owner, run_id) or {}, reference)
        review.limitations.append('This is a separate Deepgram transcription pass; the original recognizer may use the same model family.')
        review.limitations.append(f"Reference provider settings: model={os.getenv('DEEPGRAM_MODEL', 'nova-2')}, language={os.getenv('DEEPGRAM_LANGUAGE', 'en')}. Language support is not proof of accuracy.")
        store.save(owner, run_id, reference=reference.model_dump(mode='json'), review=review.model_dump(mode='json'))
    except Exception:
        # Do not persist provider errors, URLs, response bodies, credentials, or transcript fragments.
        existing = store.read(owner, run_id) or {}
        review = STTReview(status='failed', audio=AudioInfo.model_validate(existing.get('audio_info') or {}), reference_source='deepgram', issues=['Recording retrieval or reference transcription failed. No transcript quality rate is available. Retry after checking provider availability.'])
        store.save(owner, run_id, review=review.model_dump(mode='json'))
    return state_for_run(run, store.read(owner, run_id))


def _compare_saved(run: dict, stored: dict, reference: Transcript) -> STTReview:
    info = AudioInfo.model_validate(stored.get('audio_info') or {})
    original = original_transcript(run)
    if stored.get('annotations'):
        annotation = Transcript.model_validate(stored['annotations'])
        if annotation.audio_sha256 != info.sha256:
            raise ValueError('Saved annotations do not match the recording')
        original = validate_bolna_annotations(original, annotation)
    return compare_with_automatic_alignment(original, reference, info)


def restore_reference(run: dict, owner: str, reference: Transcript, store: STTReviewStore) -> dict:
    """Restore an operator-held provider result, bound to the actual cached audio."""
    stored = store.read(owner, run['run_id']) or {}
    if (not stored.get('audio') or reference.source != 'deepgram' or reference.human_verified
            or not reference.segments or reference.audio_sha256 != (stored.get('audio_info') or {}).get('sha256')):
        raise ValueError('Saved reference must match the retained recording and automatic provider source')
    if inspect_recording(stored['audio']).sha256 != reference.audio_sha256:
        raise ValueError('Retained audio bytes do not match the saved reference')
    if stored.get('reference') and stored['reference'] != reference.model_dump(mode='json'):
        raise ValueError('A different reference is already retained; it was not overwritten')
    review = _compare_saved(run, stored, reference)
    review.limitations.append('Automatic provider output restored by the authorized operator from the saved result for this recording. No new transcription was submitted.')
    store.save(owner, run['run_id'], reference=reference.model_dump(mode='json'), review=review.model_dump(mode='json'))
    return state_for_run(run, store.read(owner, run['run_id']))


def evaluate_run(run: dict, owner: str, request: CompareRequest, store: STTReviewStore) -> dict:
    stored = store.read(owner, run['run_id']) or {}
    info = AudioInfo.model_validate(stored.get('audio_info') or {})
    original = Transcript.model_validate(state_for_run(run, stored)['bolna'])
    if request.bolna_annotations:
        original = validate_bolna_annotations(original, request.bolna_annotations)
    reference_data = request.human_reference or stored.get('reference')
    reference = None
    if reference_data is None:
        review = STTReview(audio=info, issues=['No independent or human-verified reference is available.'])
    else:
        reference = reference_data.model_copy(deep=True) if isinstance(reference_data, Transcript) else Transcript.model_validate(reference_data)
        if request.scope_confirmed:
            info.scope = request.recording_scope
            info.scope_basis = 'Recording speaker coverage explicitly confirmed by the reviewer after listening.'
        if request.speaker_mapping_confirmed and reference.source == 'deepgram':
            for segment in reference.segments:
                segment.role = request.speaker_roles.get(segment.speaker, 'unknown')
            roles = {segment.role for segment in reference.segments}
            reference.scope = 'unknown' if 'unknown' in roles else 'mixed' if 'agent' in roles else 'caller_only'
        if request.target == 'caller_only' and original.scope != 'unknown':
            original = original.model_copy(update={'segments': [segment for segment in original.segments if segment.role == 'caller'], 'scope': 'caller_only'})
        review = compare_with_automatic_alignment(original, reference, info)
        if reference.source == 'deepgram':
            review.limitations.append('A separate Deepgram pass is not ground truth and may share the original recognizer model family.')
    # Persist only explicit reviewer choices, never inferred speaker identities.
    # Annotations remain private and are bound to the actual cached recording.
    annotations = None
    if request.bolna_annotations and info.available and info.sha256:
        annotations = request.bolna_annotations.model_copy(update={'audio_sha256': info.sha256}).model_dump(mode='json')
    store.save(owner, run['run_id'], review=review.model_dump(mode='json'),
               reference=reference.model_dump(mode='json') if reference else None,
               audio_info=info.model_dump(mode='json'), annotations=annotations)
    return state_for_run(run, store.read(owner, run['run_id']))
