from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field


class TranscriptionResult(BaseModel):
    transcript: str
    speakers: list[dict] = Field(default_factory=list)
    words: list[dict] = Field(default_factory=list)
    language: str = "unknown"
    duration_seconds: Optional[float] = None


class STTProvider(ABC):
    name: str

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, filename: str) -> TranscriptionResult: ...
