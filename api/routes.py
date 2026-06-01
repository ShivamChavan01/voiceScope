from fastapi import APIRouter, UploadFile, File, HTTPException
from api.schemas import HealthResponse
from core.pipeline import VoiceScopePipeline
from utils.logger import logger

router = APIRouter()
_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = VoiceScopePipeline()
    return _pipeline

ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/webm", "audio/ogg", "audio/x-m4a"}
MAX_FILE_SIZE_MB = 25


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@router.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: mp3, wav, m4a, webm"
        )

    audio_bytes = await file.read()

    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large: {size_mb:.1f}MB. Max: {MAX_FILE_SIZE_MB}MB")

    logger.info(f"[API] /analyze — file={file.filename}, size={size_mb:.2f}MB")

    result = await get_pipeline().run(audio_bytes, file.filename or "upload.mp3")

    if result.get("errors") and not result.get("report"):
        raise HTTPException(status_code=500, detail={"errors": result["errors"]})

    return result