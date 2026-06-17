from agents.base import BaseAgent
from core.context import PipelineContext
from utils.logger import logger
import importlib
import os


class AgentRegistry:
    _agents: list[type[BaseAgent]] = []

    @classmethod
    def register(cls, agent_class: type[BaseAgent]):
        cls._agents.append(agent_class)
        logger.info(f"[AgentRegistry] registered agent={agent_class.name}")
        return agent_class

    @classmethod
    def get_all(cls) -> list[type[BaseAgent]]:
        return cls._agents.copy()

    @classmethod
    def run_all(cls, ctx: PipelineContext) -> PipelineContext:
        for agent_class in cls._agents:
            agent = agent_class()
            if agent.validate_input(ctx):
                ctx = agent.run_sync(ctx)
        return ctx

    @classmethod
    def clear(cls):
        cls._agents.clear()


def discover_plugins():
    plugin_modules = os.getenv("PLUGIN_AGENTS", "").split(",")
    plugin_modules = [m.strip() for m in plugin_modules if m.strip()]

    for module_path in plugin_modules:
        try:
            importlib.import_module(module_path)
            logger.info(f"[AgentRegistry] loaded plugin={module_path}")
        except Exception as e:
            logger.error(f"[AgentRegistry] failed to load plugin={module_path}: {e}")
