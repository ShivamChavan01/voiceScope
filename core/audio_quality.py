"""
Layer 8: Audio Quality Pre-Check — detect poor audio before transcription.
Layer 9: LLM Response Time Monitoring.
Layer 10: Token Usage Tracking.
"""

import time
from pydantic import BaseModel


class AudioQualityResult(BaseModel):
    quality_score: float = 1.0
    issues: list[str] = []
    should_proceed: bool = True


class AudioQualityChecker:
    """Pre-check audio quality before sending to Whisper."""

    MIN_DURATION_SECONDS = 1.0
    MAX_DURATION_SECONDS = 3600.0  # 1 hour
    MIN_SIZE_BYTES = 1000  # 1KB minimum

    def check(self, audio_bytes: bytes, filename: str = "") -> AudioQualityResult:
        issues = []

        # Size check
        if len(audio_bytes) < self.MIN_SIZE_BYTES:
            issues.append(f"audio too small ({len(audio_bytes)} bytes)")

        # Duration estimate (rough: assume 16kHz 16-bit mono = 32KB/s)
        estimated_duration = len(audio_bytes) / 32000
        if estimated_duration < self.MIN_DURATION_SECONDS:
            issues.append(f"audio too short (~{estimated_duration:.1f}s)")
        elif estimated_duration > self.MAX_DURATION_SECONDS:
            issues.append(f"audio too long (~{estimated_duration:.0f}s)")

        # Format check
        if filename:
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext and ext not in {"mp3", "wav", "m4a", "ogg", "flac", "webm", "mp4"}:
                issues.append(f"unusual audio format: {ext}")

        # Silence detection (check if mostly zeros)
        if len(audio_bytes) > 1000:
            sample = audio_bytes[:1000]
            zero_count = sample.count(b"\x00")
            silence_ratio = zero_count / len(sample)
            if silence_ratio > 0.95:
                issues.append("audio appears to be mostly silence")

        quality_score = max(0.0, 1.0 - (len(issues) * 0.25))
        should_proceed = len(issues) == 0 or (quality_score > 0.5 and len(issues) <= 1)

        return AudioQualityResult(
            quality_score=round(quality_score, 4),
            issues=issues,
            should_proceed=should_proceed,
        )


class LLMResponseTimer:
    """Track LLM response times (Layer 8)."""

    def __init__(self):
        self._start: float = 0
        self._elapsed_ms: float = 0

    def start(self):
        self._start = time.time()

    def stop(self) -> float:
        self._elapsed_ms = (time.time() - self._start) * 1000
        return self._elapsed_ms

    @property
    def elapsed_ms(self) -> float:
        return self._elapsed_ms

    def is_anomalous(self) -> bool:
        return self._elapsed_ms > 10000  # >10s is anomalous


class TokenTracker:
    """Track token usage per LLM call (Layer 9)."""

    def __init__(self):
        self._records: list[dict] = []

    def record(self, input_tokens: int, output_tokens: int, provider: str = ""):
        self._records.append({
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total": input_tokens + output_tokens,
            "provider": provider,
        })

    def get_latest(self) -> dict:
        if not self._records:
            return {}
        return self._records[-1]

    def is_anomalous(self) -> bool:
        if not self._records:
            return False
        latest = self._records[-1]
        return bool(latest["total"] > 10000)

    def get_average(self) -> dict:
        if not self._records:
            return {}
        avg_input = sum(r["input_tokens"] for r in self._records) / len(self._records)
        avg_output = sum(r["output_tokens"] for r in self._records) / len(self._records)
        return {
            "avg_input_tokens": round(avg_input),
            "avg_output_tokens": round(avg_output),
            "total_calls": len(self._records),
        }
