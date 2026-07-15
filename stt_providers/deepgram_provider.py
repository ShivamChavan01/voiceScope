import os
import aiohttp
from stt_providers.base import STTProvider, TranscriptionResult
from utils.logger import logger


class DeepgramProvider(STTProvider):
    name = "deepgram"

    async def transcribe(self, audio_bytes: bytes, filename: str) -> TranscriptionResult:
        api_key = os.getenv("DEEPGRAM_API_KEY")
        url = "https://api.deepgram.com/v1/listen"
        params = {
            "model": "nova-2",
            "smart_format": "true",
            "diarize": "true",
            "punctuate": "true",
            "language": "en",
        }
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/mpeg",
            "Accept-Encoding": "identity",
        }

        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=audio_bytes, params=params, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise Exception(f"Deepgram API error {resp.status}: {body}")
                data = await resp.json()

        channels = data.get("results", {}).get("channels", [])
        if not channels:
            raise Exception("Deepgram returned no channels")

        alt = channels[0].get("alternatives", [{}])[0]
        transcript = alt.get("transcript", "")
        language = data.get("results", {}).get("channels", [{}])[0].get("detected_language", "unknown")
        duration = data.get("metadata", {}).get("duration")

        speakers = []
        paragraphs = alt.get("paragraphs", {}).get("paragraphs", [])
        if paragraphs:
            for para in paragraphs:
                speaker_id = para.get("speaker", 0)
                text = " ".join(s.get("text", "") for s in para.get("sentences", []))
                if text.strip():
                    speakers.append({"speaker": speaker_id, "text": text.strip()})
        else:
            speakers = [{"speaker": 0, "text": transcript}]

        logger.info(f"[STT:deepgram] done — {len(transcript)} chars, lang={language}")
        return TranscriptionResult(transcript=transcript, speakers=speakers, language=language, duration_seconds=duration)
