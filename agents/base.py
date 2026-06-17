from abc import ABC, abstractmethod
from core.context import PipelineContext
from typing import Optional


class BaseAgent(ABC):
    name: str
    description: str = ""

    @abstractmethod
    async def run(self, ctx: PipelineContext, **kwargs) -> PipelineContext:
        ...

    def validate_input(self, ctx: PipelineContext) -> bool:
        return True
