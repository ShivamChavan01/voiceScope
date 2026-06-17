from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import StreamingResponse
from api.schemas import HealthResponse
from api.sse import stream_analysis
from core.pipeline import VoiceScopePipeline
from core.batch import BatchProcessor
from storage.cost_store import CostStore
from utils.logger import logger
from utils.security import hash_api_key, sanitize_log_input
from typing import Optional

router = APIRouter()
_pipeline = None
_cost_store = None
_batch_processor = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = VoiceScopePipeline()
    return _pipeline


def get_cost_store():
    global _cost_store
    if _cost_store is None:
        _cost_store = CostStore()
    return _cost_store


def get_batch_processor():
    global _batch_processor
    if _batch_processor is None:
        _batch_processor = BatchProcessor()
    return _batch_processor


ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/webm",
    "audio/ogg",
    "audio/x-m4a",
}
MAX_FILE_SIZE_MB = 25


def _validate_audio(file: UploadFile, audio_bytes: bytes):
    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: mp3, wav, m4a, webm",
        )
    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400, detail=f"File too large: {size_mb:.1f}MB. Max: {MAX_FILE_SIZE_MB}MB"
        )
    return size_mb


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@router.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    size_mb = _validate_audio(file, audio_bytes)

    logger.info(f"[API] /analyze — file={sanitize_log_input(file.filename)}, size={size_mb:.2f}MB")

    result = await get_pipeline().run(audio_bytes, file.filename or "upload.mp3")

    if result.get("provider", {}).get("name"):
        p = result["provider"]
        await get_cost_store().log_cost(
            run_id=result["run_id"],
            provider=p["name"],
            model=p["model"],
            input_tokens=p["input_tokens"],
            output_tokens=p["output_tokens"],
            cost_usd=p["cost_usd"],
        )

    if result.get("errors") and not result.get("report"):
        raise HTTPException(status_code=500, detail="Analysis failed")

    return result


@router.post("/analyze/stream")
async def analyze_audio_stream(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    size_mb = _validate_audio(file, audio_bytes)

    logger.info(
        f"[API] /analyze/stream — file={sanitize_log_input(file.filename)}, size={size_mb:.2f}MB"
    )

    return StreamingResponse(
        stream_analysis(audio_bytes, file.filename or "upload.mp3"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/batch")
async def create_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    callback_url: Optional[str] = Form(None),
):
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per batch")

    api_key = request.headers.get("X-API-Key", "")
    owner_key = hash_api_key(api_key) if api_key else None

    file_data = []
    for file in files:
        if file.content_type not in ALLOWED_AUDIO_TYPES:
            raise HTTPException(
                status_code=400, detail=f"Unsupported file type: {file.content_type}"
            )
        audio_bytes = await file.read()
        if len(audio_bytes) / (1024 * 1024) > MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400, detail=f"File too large: {sanitize_log_input(file.filename)}"
            )
        file_data.append((audio_bytes, file.filename or "upload.mp3"))

    try:
        batch_id = await get_batch_processor().create_batch(file_data, callback_url, owner_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"batch_id": batch_id, "status": "processing", "total_files": len(files)}


@router.get("/batch/{batch_id}")
async def get_batch_status(request: Request, batch_id: str):
    api_key = request.headers.get("X-API-Key", "")
    owner_key = hash_api_key(api_key)
    batch = get_batch_processor().get_batch(batch_id, owner_key)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {
        "batch_id": batch["batch_id"],
        "status": batch["status"],
        "total": batch["total"],
        "completed": batch["completed"],
        "failed": batch["failed"],
    }


@router.get("/batch/{batch_id}/results")
async def get_batch_results(request: Request, batch_id: str):
    api_key = request.headers.get("X-API-Key", "")
    owner_key = hash_api_key(api_key)
    batch = get_batch_processor().get_batch(batch_id, owner_key)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch["status"] != "completed":
        raise HTTPException(status_code=400, detail="Batch still processing")
    return {"batch_id": batch_id, "results": batch["results"]}


@router.get("/costs")
async def get_costs():
    return await get_cost_store().get_summary()
