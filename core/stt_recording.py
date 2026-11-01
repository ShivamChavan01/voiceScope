"""Bounded recording retrieval with DNS pinning and explicit redirect credential handling."""

import hashlib
import io
import ipaddress
import os
import socket
import wave
from urllib.parse import urljoin, urlparse
from uuid import UUID

import aiohttp
from aiohttp.abc import AbstractResolver

from core.stt_quality import AudioInfo

MAX_RECORDING_BYTES = 25 * 1024 * 1024


def public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast


class PublicResolver(AbstractResolver):
    async def resolve(self, host, port=0, family=socket.AF_INET):
        import asyncio
        answers = await asyncio.get_running_loop().getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
        if not answers or any(not public_ip(answer[4][0]) for answer in answers):
            raise OSError('Recording host is not public')
        return [{'hostname': host, 'host': item[4][0], 'port': port, 'family': item[0], 'proto': item[2], 'flags': socket.AI_NUMERICHOST} for item in answers]

    async def close(self):
        pass


def valid_recording_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
            return False
        try:
            return public_ip(parsed.hostname)
        except ValueError:
            return True  # Hostname resolution is pinned and validated by PublicResolver.
    except ValueError:
        return False


async def retrieve_bolna_recording(call_id: str) -> tuple[bytes, str]:
    execution = str(UUID(call_id))
    key = os.getenv('BOLNA_API_KEY')
    if not key:
        raise ValueError('Bolna recording credentials unavailable')
    url = f'https://api.bolna.ai/recordings/call/{execution}'
    return await download_recording(url, {'Authorization': f'Bearer {key}'})


async def download_recording(url: str, headers: dict[str, str] | None = None) -> tuple[bytes, str]:
    """Stream bounded audio, pin public DNS and strip credentials across hosts."""
    from core.staging import require_live_services
    require_live_services()
    credential_host = urlparse(url).hostname
    connector = aiohttp.TCPConnector(resolver=PublicResolver(), use_dns_cache=False)
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=60)) as session:
        for _ in range(5):
            if not valid_recording_url(url):
                raise ValueError('Recording redirect rejected')
            request_headers = (headers or {}) if urlparse(url).hostname == credential_host else {}
            async with session.get(url, headers=request_headers, allow_redirects=False) as response:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get('Location')
                    if not location:
                        raise ValueError('Recording redirect missing destination')
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    raise ValueError('Original recording could not be retrieved')
                content_type = response.headers.get('Content-Type', '').split(';')[0]
                if not content_type.startswith('audio/'):
                    raise ValueError('Recording response is not audio')
                if response.content_length is not None and response.content_length > MAX_RECORDING_BYTES:
                    raise ValueError('Recording exceeds 25 MB')
                data = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    data.extend(chunk)
                    if len(data) > MAX_RECORDING_BYTES:
                        raise ValueError('Recording exceeds 25 MB')
                if not data:
                    raise ValueError('Recording is empty')
                return bytes(data), content_type
    raise ValueError('Recording redirect limit exceeded')


def inspect_recording(data: bytes) -> AudioInfo:
    info = AudioInfo(available=bool(data), sha256=hashlib.sha256(data).hexdigest() if data else None)
    try:
        with wave.open(io.BytesIO(data), 'rb') as recording:
            info.channels = recording.getnchannels()
            duration = recording.getnframes() / recording.getframerate()
            info.duration_seconds = duration if duration > 0 else None
    except (wave.Error, EOFError):
        pass
    return info
