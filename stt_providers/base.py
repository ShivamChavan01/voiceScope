from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


class TranscriptionResult(BaseModel):
    transcript: str
    speakers: list[dict] = []
    language: str = "unknown"
    duration_seconds: Optional[float] = None


class STTProvider(ABC):
    name: str

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, filename: str) -> TranscriptionResult: ...
