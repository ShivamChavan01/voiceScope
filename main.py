from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router


load_dotenv()

app = FastAPI(
    title="VoiceScope",
    description="Open source observability API for voice AI agents. 3-stage agentic pipeline: transcription → analysis → report.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": "VoiceScope",
        "docs": "/docs",
        "health": "/api/v1/health",
        "analyze": "POST /api/v1/analyze"
    }
