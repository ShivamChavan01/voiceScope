import httpx
from sdk.voicescope.models import AnalysisReport, BatchResult
from typing import Optional


class VoiceScope:
    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key}

    async def analyze(self, file_path: str) -> AnalysisReport:
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(file_path, "rb") as f:
                response = await client.post(
                    f"{self.base_url}/api/v1/analyze",
                    headers=self.headers,
                    files={"file": (file_path, f, "audio/mpeg")},
                )
            response.raise_for_status()
            return AnalysisReport(**response.json())

    def analyze_sync(self, file_path: str) -> AnalysisReport:
        import asyncio
        return asyncio.run(self.analyze(file_path))

    async def analyze_batch(self, file_paths: list[str], callback_url: Optional[str] = None) -> BatchResult:
        async with httpx.AsyncClient(timeout=120.0) as client:
            files = []
            for path in file_paths:
                f = open(path, "rb")
                files.append(("files", (path, f, "audio/mpeg")))

            data = {}
            if callback_url:
                data["callback_url"] = callback_url

            response = await client.post(
                f"{self.base_url}/api/v1/batch",
                headers=self.headers,
                files=files,
                data=data,
            )

            for _, (_, f, _) in files:
                f.close()

            response.raise_for_status()
            return BatchResult(**response.json())

    async def get_batch_status(self, batch_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/batch/{batch_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_costs(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/costs",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()
