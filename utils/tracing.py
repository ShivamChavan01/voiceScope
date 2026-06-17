import uuid
import time
from contextvars import ContextVar
from pydantic import BaseModel
from typing import Optional


class StageTiming(BaseModel):
    stage: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None


class RequestContext(BaseModel):
    run_id: str = ""
    correlation_id: str = ""
    stage_timings: list[StageTiming] = []
    start_time: float = 0.0

    def start_stage(self, stage: str):
        self.stage_timings.append(StageTiming(
            stage=stage,
            start_time=time.time()
        ))

    def end_stage(self, stage: str):
        for timing in self.stage_timings:
            if timing.stage == stage and timing.end_time is None:
                timing.end_time = time.time()
                timing.duration_ms = (timing.end_time - timing.start_time) * 1000
                break

    def get_total_duration_ms(self) -> float:
        if not self.stage_timings:
            return 0.0
        return sum(t.duration_ms or 0 for t in self.stage_timings)

    def get_stage_summary(self) -> dict:
        return {
            t.stage: {"duration_ms": t.duration_ms}
            for t in self.stage_timings
            if t.duration_ms is not None
        }


_request_context: ContextVar[RequestContext] = ContextVar("request_context")


def get_request_context() -> RequestContext:
    ctx = _request_context.get(None)
    if ctx is None:
        ctx = RequestContext(
            run_id=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            start_time=time.time()
        )
        _request_context.set(ctx)
    return ctx


def set_request_context(ctx: RequestContext):
    _request_context.set(ctx)
