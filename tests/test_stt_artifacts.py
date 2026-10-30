import asyncio
import io
import socket
import wave
from unittest.mock import AsyncMock, patch

import pytest

from core.stt_recording import PublicResolver, inspect_recording, valid_recording_url
from core.stt_sources import bolna_transcript, deepgram_reference, validate_bolna_annotations
from core.stt_quality import Transcript
from storage.stt_reviews import STTReviewStore
from stt_providers.base import TranscriptionResult


def test_private_store_is_owner_scoped_expiring_and_deletable(tmp_path):
    store = STTReviewStore(tmp_path / 'private')
    store.save('owner-a', 'run', audio=b'private audio', audio_info={'available': True}, reference={'source': 'human'}, review={'status': 'blocked'})
    assert store.read('owner-b', 'run') is None
    assert store.read('owner-a', 'run')['audio'] == b'private audio'
    store.save('owner-a', 'run', review={'status': 'completed'})
    assert store.read('owner-a', 'run')['reference'] == {'source': 'human'}
    assert store.path.stat().st_mode & 0o077 == 0
    with patch('storage.stt_reviews.time.time', return_value=10**12):
        assert store.read('owner-a', 'run') is None
    store.delete_run('run')
    assert store.read('owner-a', 'run') is None


def test_channel_count_does_not_prove_caller_isolation():
    out = io.BytesIO()
    with wave.open(out, 'wb') as recording:
        recording.setnchannels(2)
        recording.setsampwidth(2)
        recording.setframerate(8000)
        recording.writeframes(b'\x00' * 32000)
    info = inspect_recording(out.getvalue())
    assert info.channels == 2
    assert info.duration_seconds == 1
    assert info.scope == 'unknown'
    assert inspect_recording(b'not a wav').channels is None
    assert inspect_recording(b'').available is False


@pytest.mark.parametrize('url', ['http://example.com', 'https://127.0.0.1', 'https://[::1]', 'https://169.254.169.254', 'https://user:pass@example.com', 'https://example.com:80', 'https://224.0.0.1'])
def test_recording_url_rejects_unsafe_destinations(url):
    assert not valid_recording_url(url)


async def test_resolver_rejects_private_dns_and_returns_pinned_public_addresses():
    answer = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('127.0.0.1', 443))]
    with patch.object(asyncio.get_running_loop(), 'getaddrinfo', new=AsyncMock(return_value=answer)):
        with pytest.raises(OSError):
            await PublicResolver().resolve('public-looking.example', 443)
    answer[0] = (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('1.1.1.1', 443))
    with patch.object(asyncio.get_running_loop(), 'getaddrinfo', new=AsyncMock(return_value=answer)):
        assert (await PublicResolver().resolve('example.com', 443))[0]['host'] == '1.1.1.1'
    await PublicResolver().close()


def test_bolna_text_keeps_absent_timestamps_and_explicit_roles():
    document = bolna_transcript('assistant: Hello\nuser: I need a refund')
    assert document.scope == 'mixed'
    assert document.segments[1].role == 'caller'
    assert document.segments[1].start is None
    assert bolna_transcript('Only unlabelled words').scope == 'unknown'
    assert bolna_transcript('').segments == []


def test_deepgram_reference_preserves_speaker_ids_without_guessing_caller():
    result = TranscriptionResult(transcript='Hello there', words=[
        {'word': 'Hello', 'speaker': 1, 'start': 0, 'end': 0.5},
        {'word': 'there', 'speaker': 1, 'start': 0.5, 'end': 1},
    ])
    document = deepgram_reference(result, 'a' * 64)
    assert document.segments[0].text == 'Hello there'
    assert document.segments[0].end == 1
    assert document.segments[0].speaker == 'dg_1'
    assert document.segments[0].role == 'unknown'
    assert document.scope == 'unknown'
    assert deepgram_reference(TranscriptionResult(transcript='Hello'), 'a' * 64).segments[0].start is None


@pytest.mark.parametrize('start,end', [(None, 1), (0, None), (True, 1), (0, False), (-1, 1), (0, float('inf')), (float('nan'), 1), (2, 1)])
def test_invalid_word_times_remain_unscored_without_breaking_adjacent_speech(start, end):
    result = TranscriptionResult(transcript='First uncertain last', words=[
        {'word': 'First', 'speaker': 0, 'start': 0, 'end': 0.4},
        {'word': 'uncertain', 'speaker': 0, 'start': start, 'end': end},
        {'word': 'last', 'speaker': 0, 'start': 1.5, 'end': 2},
    ])
    reference = deepgram_reference(result, 'a' * 64)
    assert [segment.text for segment in reference.segments] == ['First', 'uncertain', 'last']
    assert reference.segments[1].start is None
    assert reference.segments[1].end is None
    assert reference.segments[0].start == 0
    assert reference.segments[2].start == 1.5
    assert all(segment.role == 'unknown' for segment in reference.segments)


def test_timing_annotations_cannot_rewrite_original_words_or_roles():
    original = bolna_transcript('user: I do not want a refund')
    annotated = original.model_copy(deep=True)
    annotated.segments[0].start, annotated.segments[0].end = 1, 3
    assert validate_bolna_annotations(original, annotated) == annotated
    annotated.segments[0].text = 'I do want a refund'
    with pytest.raises(ValueError):
        validate_bolna_annotations(original, annotated)
    with pytest.raises(ValueError):
        validate_bolna_annotations(original, Transcript(source='deepgram'))


def test_deepgram_turns_split_on_pause_and_invalid_timing_is_not_invented():
    result = TranscriptionResult(transcript='Hi. There.', words=[
        {'word': 'Hi', 'speaker': 0, 'start': 0, 'end': 0.4},
        {'word': 'there', 'speaker': 0, 'start': 5, 'end': 5.5},
        {'word': 'last', 'speaker': 0, 'start': float('nan'), 'end': 7},
    ])
    doc = deepgram_reference(result, 'a' * 64)
    assert len(doc.segments) == 3
    assert doc.segments[1].start == 5
    assert doc.segments[2].start is None


async def test_recording_download_strips_credentials_on_redirect_and_bounds_payload(monkeypatch):
    from core.stt_recording import retrieve_bolna_recording
    monkeypatch.setenv('BOLNA_API_KEY', 'private-test-value')
    requests = []

    class Content:
        async def iter_chunked(self, size):
            yield b'original audio'

    class Response:
        def __init__(self, status, headers):
            self.status, self.headers = status, headers
            self.content_length = None
            self.content = Content()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    responses = [Response(302, {'Location': 'https://recordings.example/audio.wav'}), Response(200, {'Content-Type': 'audio/wav'})]

    class Session:
        def __init__(self, **kwargs):
            self.connector = kwargs['connector']

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            await self.connector.close()

        def get(self, url, **kwargs):
            requests.append((url, kwargs))
            return responses.pop(0)

    with patch('core.stt_recording.aiohttp.ClientSession', Session):
        data, content_type = await retrieve_bolna_recording('00000000-0000-0000-0000-000000000001')
    assert data == b'original audio'
    assert content_type == 'audio/wav'
    assert requests[0][1]['headers']['Authorization'] == 'Bearer private-test-value'
    assert requests[1][1]['headers'] == {}
    responses[:] = [Response(302, {'Location': 'https://127.0.0.1/private'})]
    with patch('core.stt_recording.aiohttp.ClientSession', Session):
        with pytest.raises(ValueError, match='redirect rejected'):
            await retrieve_bolna_recording('00000000-0000-0000-0000-000000000001')
    responses[:] = [Response(200, {'Content-Type': 'audio/wav'})]
    with patch('core.stt_recording.aiohttp.ClientSession', Session), patch('core.stt_recording.MAX_RECORDING_BYTES', 4):
        with pytest.raises(ValueError, match='exceeds'):
            await retrieve_bolna_recording('00000000-0000-0000-0000-000000000001')


def test_saving_after_expiry_cannot_restore_old_recordings_or_references(tmp_path):
    store = STTReviewStore(tmp_path / 'private')
    with patch('storage.stt_reviews.time.time', return_value=1000):
        store.save('owner', 'run', audio=b'expired private recording',
                   audio_info={'available': True}, reference={'source': 'human'},
                   review={'status': 'completed'})
    with patch('storage.stt_reviews.time.time', return_value=1000 + 86401):
        assert store.read('owner', 'run') is None
        store.save('owner', 'run', review={'status': 'blocked'})
        saved = store.read('owner', 'run')
    assert saved['review'] == {'status': 'blocked'}
    assert saved['audio'] is None
    assert saved['audio_info'] is None
    assert saved['reference'] is None


def test_private_annotations_migrate_and_expire_with_the_recording(tmp_path):
    import sqlite3
    directory = tmp_path / 'private'
    directory.mkdir()
    with sqlite3.connect(directory / 'reviews.sqlite') as conn:
        conn.execute('CREATE TABLE stt_artifacts (owner TEXT, run_id TEXT, expires REAL, audio BLOB, content_type TEXT, audio_info TEXT, reference TEXT, review TEXT, PRIMARY KEY(owner, run_id))')
        conn.execute('INSERT INTO stt_artifacts(owner,run_id,expires,audio) VALUES(?,?,?,?)', ('owner', 'run', 10**12, b'original audio'))
    store = STTReviewStore(directory)
    assert store.read('owner', 'run')['audio'] == b'original audio'
    with patch('storage.stt_reviews.time.time', return_value=1000):
        store.save('owner', 'run', annotations={'source': 'bolna', 'segments': []})
        assert store.read('owner', 'run')['annotations']['source'] == 'bolna'
        assert store.read('another-owner', 'run') is None
    with patch('storage.stt_reviews.time.time', return_value=87401):
        store.save('owner', 'run', review={'status': 'blocked'})
        assert store.read('owner', 'run')['annotations'] is None
        assert store.read('owner', 'run')['audio'] is None
