"""
Demo data seeder — populates the dashboard with realistic analyzed calls so a
fresh clone shows the product working immediately.

Run via: `voicescope demo` or `POST /api/v1/demo/seed`.
Seeding is idempotent (run_ids are fixed, log_run upserts).
"""

from utils.logger import logger
from core.harness import ValidationHarness


def _run(
    run_id: str,
    intent: str,
    sentiment: str,
    outcome: str,
    hallucination: bool,
    escalation: bool,
    transcript: str,
    evidence: str = "",
    policy: str = "",
    findings: list[str] | None = None,
    quality: int | None = None,
    duration: float = 180,
    provider: str = "synthetic",
    model: str = "fixture-no-model",
    cost: float = 0.0,
) -> dict:
    word_count = len(transcript.split())
    return {
        "run_id": run_id,
        "raw_transcript": transcript,
        "transcript_speakers": None,
        "errors": [],
        "status": "completed",
        "report": {
            "quality_score": quality,
            "executive_summary": "",
        },
        "analysis": {
            "intent": intent,
            "sentiment_arc": sentiment,
            "hallucination_detected": hallucination,
            "hallucination_evidence": evidence,
            "policy_evidence": policy,
            "outcome": outcome,
            "escalation_signal": escalation,
            "findings": findings or [],
        },
        "provider": {
            "name": provider,
            "model": model,
            "cost_usd": cost,
            "input_tokens": 0,
            "output_tokens": 0,
        },
        "transcript_meta": {
            "language": "en",
            "duration_seconds": duration,
            "char_count": len(transcript),
            "word_count": word_count,
            "chunk_count": None,
        },
    }


# ─── Sample calls ──────────────────────────────────────────────────────

_SAMPLES: list[dict] = [
    {
        "run_id": "demo-001",
        "intent": "cancel subscription",
        "sentiment": "negative",
        "outcome": "resolved",
        "hallucination": False,
        "escalation": False,
        "transcript": (
            "Agent: Thank you for calling. How can I help you today?\n"
            "Customer: I want to cancel my subscription. I keep getting charged.\n"
            "Agent: I'm sorry to hear that. I can cancel it for you right now.\n"
            "Customer: Thank you.\n"
            "Agent: Done. Your subscription is canceled and you won't be charged again.\n"
            "Customer: Great, thanks for the help."
        ),
    },
    {
        "run_id": "demo-002",
        "intent": "billing dispute duplicate charge",
        "sentiment": "negative",
        "outcome": "resolved",
        "hallucination": False,
        "escalation": False,
        "transcript": (
            "Customer: I was charged $49.99 twice for my subscription. This is unacceptable.\n"
            "Agent: I apologize. I can see the duplicate charge and I've processed a refund of $49.99.\n"
            "Customer: How long will that take?\n"
            "Agent: It typically appears within 3 to 5 business days.\n"
            "Customer: Thank you, that's great."
        ),
    },
    {
        "run_id": "demo-003",
        "intent": "refund request over $50",
        "sentiment": "neutral",
        "outcome": "unresolved",
        "hallucination": True,
        "escalation": False,
        "evidence": (
            "Agent promised 'I can guarantee a same-day refund.' This contradicts the "
            "refund policy that agents cannot guarantee same-day refunds under any circumstances."
        ),
        "policy": (
            'Claim: "I can guarantee a same-day refund."\n'
            "Relevant Policy:\n"
            "Agents cannot guarantee same-day refunds under any circumstances."
        ),
        "findings": [
            "customer requested a $120 refund",
            "agent promised same-day refund",
            "refund exceeds $50 supervisor threshold",
        ],
        "transcript": (
            "Customer: I'd like a refund for this $120 order. It arrived damaged.\n"
            "Agent: I'm sorry about that. I can guarantee a same-day refund for you.\n"
            "Customer: Really? That would be great.\n"
            "Agent: Absolutely, you'll see it back today."
        ),
    },
    {
        "run_id": "demo-004",
        "intent": "request to speak with supervisor",
        "sentiment": "negative",
        "outcome": "escalated",
        "hallucination": False,
        "escalation": True,
        "transcript": (
            "Customer: This is the third time I'm calling about the same issue.\n"
            "Agent: I understand your frustration.\n"
            "Customer: I want to speak to a supervisor. Now.\n"
            "Agent: Of course, I'll transfer you right away."
        ),
    },
    {
        "run_id": "demo-005",
        "intent": "shipping question",
        "sentiment": "neutral",
        "outcome": "unresolved",
        "hallucination": True,
        "escalation": False,
        "evidence": (
            "Agent promised free express shipping on a $30 order. The policy states free "
            "shipping applies only to orders over $50."
        ),
        "policy": (
            'Claim: "You get free express shipping."\n'
            "Relevant Policy:\n"
            "Free shipping is available on orders over $50."
        ),
        "findings": [
            "customer asked about shipping for a $30 order",
            "agent promised free express shipping",
        ],
        "transcript": (
            "Customer: How much is express shipping on this $30 order?\n"
            "Agent: Don't worry, you get free express shipping.\n"
            "Customer: Oh nice.\n"
            "Agent: Yes, it will arrive in 2 days."
        ),
    },
    {
        "run_id": "demo-006",
        "intent": "technical support router",
        "sentiment": "positive",
        "outcome": "resolved",
        "hallucination": False,
        "escalation": False,
        "transcript": (
            "Customer: My router won't connect to the internet.\n"
            "Agent: Let's walk through this. Can you power cycle the router?\n"
            "Customer: Done. It's back online now.\n"
            "Agent: Excellent. Anything else I can help with?\n"
            "Customer: No, that did it. Thank you so much."
        ),
    },
    {
        "run_id": "demo-007",
        "intent": "legal action threat",
        "sentiment": "negative",
        "outcome": "escalated",
        "hallucination": False,
        "escalation": True,
        "transcript": (
            "Customer: If this isn't resolved today I'm taking legal action.\n"
            "Agent: I understand. Let me escalate this to our legal team right away.\n"
            "Customer: Fine.\n"
            "Agent: I've documented the call and escalated it now."
        ),
    },
    {
        "run_id": "demo-008",
        "intent": "order status",
        "sentiment": "neutral",
        "outcome": "resolved",
        "hallucination": False,
        "escalation": False,
        "transcript": (
            "Customer: Where is my order?\n"
            "Agent: Let me check. It shipped yesterday and should arrive within 5 to 7 business days.\n"
            "Customer: Okay, thanks.\n"
            "Agent: You're welcome. Is there anything else?"
        ),
    },
]


async def seed_demo_runs(store=None, reset: bool = False) -> dict:
    """Insert demo calls into the monitoring store. Idempotent by design."""
    from storage.monitoring import MonitoringStore

    store = store or MonitoringStore()

    seeded = 0
    for s in _SAMPLES:
        result = _run(
            run_id=s["run_id"],
            intent=s["intent"],
            sentiment=s["sentiment"],
            outcome=s["outcome"],
            hallucination=s["hallucination"],
            escalation=s["escalation"],
            transcript=s["transcript"],
            evidence=s.get("evidence", ""),
            policy=s.get("policy", ""),
            findings=s.get("findings"),
        )
        harness = ValidationHarness().validate_analysis(result["analysis"], s["transcript"])
        result["harness"] = harness.model_dump()
        result["data_source"] = "synthetic_demo"
        result["score_contract"] = "heuristic_consistency_v2"
        if not harness.validation_passed:
            result["status"] = "partial"
        await store.log_run(result, harness)
        seeded += 1

    logger.info(f"[DemoSeed] seeded {seeded} demo runs")
    return {"seeded": seeded, "total_runs": seeded}


async def reset_demo_runs(store=None) -> dict:
    """Remove demo runs (used by CLI --reset)."""
    from storage.monitoring import MonitoringStore

    store = store or MonitoringStore()
    for s in _SAMPLES:
        try:
            await store.delete_run(s["run_id"])
        except Exception:
            pass
    return {"reset": True, "removed": len(_SAMPLES)}
