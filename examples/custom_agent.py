from agents.base import BaseAgent
from agents.registry import AgentRegistry
from core.context import PipelineContext


@AgentRegistry.register
class ComplianceCheckAgent(BaseAgent):
    name = "compliance_check"
    description = "Checks transcript for compliance violations"

    async def run(self, ctx: PipelineContext, **kwargs) -> PipelineContext:
        if not ctx.raw_transcript:
            return ctx

        violations = []
        lower = ctx.raw_transcript.lower()

        if any(phrase in lower for phrase in ["social security", "credit card number", "password"]):
            violations.append("PII mentions detected")

        ctx.report = ctx.report or {}
        ctx.report["compliance"] = {
            "violations": violations,
            "passed": len(violations) == 0,
        }

        ctx.mark_stage("compliance_check")
        return ctx
