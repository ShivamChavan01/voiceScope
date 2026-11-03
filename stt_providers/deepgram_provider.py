import os

import aiohttp

from stt_providers.base import STTProvider, TranscriptionResult
from utils.logger import logger


def speaker_segments(alternative: dict) -> list[dict]:
    """Keep real diarization; absence of speaker IDs is not a single-speaker call."""
    paragraphs = (alternative.get("paragraphs") or {}).get("paragraphs", [])
    if paragraphs and all(isinstance(para.get("speaker"), int) for para in paragraphs):
        turns = [
            {"speaker": para["speaker"], "text": " ".join(sentence.get("text", "") for sentence in para.get("sentences", []))}
            for para in paragraphs
        ]
        if all(turn["text"].strip() for turn in turns):
            return turns
    words = alternative.get("words") or []
    if words and all(isinstance(word.get("speaker"), int) for word in words):
        turns = []
        for word in words:
            text = word.get("punctuated_word") or word.get("word", "")
            if turns and turns[-1]["speaker"] == word["speaker"]:
                turns[-1]["text"] += " " + text
            else:
                turns.append({"speaker": word["speaker"], "text": text})
        return turns
    transcript = alternative.get("transcript", "")
    return [{"speaker": 0, "text": transcript, "diarization_source": "unavailable"}] if transcript else []


class DeepgramProvider(STTProvider):
    name = "deepgram"

    async def transcribe(self, audio_bytes: bytes, filename: str) -> TranscriptionResult:
        api_key = os.getenv("DEEPGRAM_API_KEY")
        model = os.getenv('DEEPGRAM_MODEL', 'nova-2')
        language_option = os.getenv('DEEPGRAM_LANGUAGE', 'en')
        if model not in ('nova-2', 'nova-3') or language_option not in ('en', 'multi'):
            raise ValueError('Unsupported Deepgram model/language configuration')
        if language_option == 'multi' and model != 'nova-3':
            raise ValueError('Multilingual QA transcription requires Nova-3')
        url = "https://api.deepgram.com/v1/listen"
        params = {
            "model": model,
            "smart_format": "true",
            "diarize": "true",
            "paragraphs": "true",
            "punctuate": "true",
            "language": language_option,
        }
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/wav" if filename.lower().endswith('.wav') else "audio/mpeg",
            "Accept-Encoding": "identity",
        }

        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=audio_bytes, params=params, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Deepgram API error {resp.status}")
                data = await resp.json()

        channels = data.get("results", {}).get("channels", [])
        if not channels:
            raise Exception("Deepgram returned no channels")

        alt = channels[0].get("alternatives", [{}])[0]
        transcript = alt.get("transcript", "")
        language = data.get("results", {}).get("channels", [{}])[0].get("detected_language", "unknown")
        duration = data.get("metadata", {}).get("duration")

        speakers = speaker_segments(alt)

        logger.info(f"[STT:deepgram] done — {len(transcript)} chars, lang={language}")
        return TranscriptionResult(transcript=transcript, speakers=speakers, words=alt.get("words") or [], language=language, duration_seconds=duration)
