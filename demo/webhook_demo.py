#!/usr/bin/env python3
"""
VoiceScope Webhook Demo — Simulates real webhook calls from 6 platforms.

Usage:
    1. Start VoiceScope:  uvicorn main:app --reload
    2. Run this demo:     python demo/webhook_demo.py

Requires: VALID_API_KEYS env var set, LLM provider configured.
"""

import httpx
import json
import sys
import time

BASE_URL = "http://localhost:8000"
API_KEY = "demo-key-voicescope"

# ─── Platform Payloads ───────────────────────────────────────────────

VAPI_PAYLOAD = {
    "message": {
        "type": "end-of-call-report",
        "endedReason": "hangup",
        "call": {
            "id": "7420f27a-30fd-4f49-a995-5549ae7cc00d",
            "orgId": "eb166faa-7145-46ef-8044-589b47ae3b56",
            "type": "outboundPhoneCall",
            "status": "ended",
            "startedAt": "2024-09-10T11:14:15.000Z",
            "endedAt": "2024-09-10T11:15:30.000Z",
            "cost": 0.05,
            "assistantId": "5b0a4a08-133c-4146-9315-0984f8c6be80",
            "recordingUrl": "https://storage.vapi.ai/7420f27a-recording.mp3",
        },
        "artifact": {
            "recording": {
                "monoUrl": "https://storage.vapi.ai/7420f27a-mono.mp3",
                "stereoUrl": "https://storage.vapi.ai/7420f27a-stereo.mp3",
            },
            "transcript": (
                "AI: Thank you for calling Acme Support. How can I help you today?\n"
                "Customer: Hi, I need to cancel my subscription.\n"
                "AI: I'm sorry to hear that. May I ask why you'd like to cancel?\n"
                "Customer: I found a cheaper alternative.\n"
                "AI: I understand. We do offer a 20% discount for annual plans. Would you like to consider that?\n"
                "Customer: No, I've already decided. Please cancel it.\n"
                "AI: Alright, I've processed your cancellation. You'll receive a confirmation email shortly.\n"
                "Customer: Thank you.\n"
                "AI: You're welcome. Have a great day!"
            ),
        },
    }
}

RETELL_PAYLOAD = {
    "event": "call_ended",
    "call": {
        "call_type": "phone_call",
        "from_number": "+12137771234",
        "to_number": "+12137771235",
        "direction": "inbound",
        "call_id": "Jabr9TXYYJHfvl6Syypi88rdAHYHmcq6",
        "agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
        "agent_name": "Sales Agent",
        "call_status": "ended",
        "start_timestamp": 1714608475945,
        "end_timestamp": 1714608491736,
        "duration_ms": 15791,
        "disconnection_reason": "user_hangup",
        "transcript": (
            "Agent: Hi, this is Sarah from TechCorp. Am I speaking with John?\n"
            "Customer: Yes, this is John.\n"
            "Agent: Great! I'm calling about your demo request. Do you have 2 minutes?\n"
            "Customer: Sure, go ahead.\n"
            "Agent: Perfect. I see you requested a demo for our enterprise plan. What's your main use case?\n"
            "Customer: We need to process about 10,000 calls per month for our support team.\n"
            "Agent: That's a great fit. Our enterprise plan handles that with room to grow. Shall I schedule a demo for this week?\n"
            "Customer: Yes, Thursday works.\n"
            "Agent: Thursday at 2pm EST. You'll get a calendar invite shortly. Thanks, John!"
        ),
        "recording_url": "https://retellai.s3.us-west-2.amazonaws.com/recording.wav",
        "call_cost": {
            "product_costs": [
                {"product": "elevenlabs_tts", "unit_price": 1, "cost": 60},
                {"product": "openai_llm", "unit_price": 0.5, "cost": 30},
            ],
            "combined_cost": 90,
        },
    },
}

BLAND_PAYLOAD = {
    "call_id": "12345678-1234-1234-1234-123456789012",
    "completed": True,
    "status": "completed",
    "concatenated_transcript": (
        "user: Hello, is this the pharmacy?\n"
        "assistant: Yes, this is MediCare Pharmacy. How can I help you?\n"
        "user: I'd like to refill my prescription for Lisinopril.\n"
        "assistant: I can help with that. What's your date of birth?\n"
        "user: March 15, 1985.\n"
        "assistant: Thank you. I see your prescription for Lisinopril 10mg. It's ready for pickup. Would you like us to hold it at the counter?\n"
        "user: Yes, please. What are your hours?\n"
        "assistant: We're open Monday through Friday, 9am to 7pm, and Saturday 10am to 2pm.\n"
        "user: Perfect, I'll pick it up tomorrow. Thank you!\n"
        "assistant: You're welcome. Have a great day!"
    ),
    "corrected_duration": "45",
    "recording_url": "https://api.twilio.com/Recordings/RE456",
    "from": "+15559876543",
    "to": "+15551234567",
    "price": 0.032,
}

BOLNA_WEBHOOK = {
    "id": 7432382142914,
    "agent_id": "3c90c3cc-0d44-4b50-8888-8dd25736052a",
    "status": "completed",
    "conversation_duration": 123,
    "total_cost": 123,
    "transcript": (
        "Agent: Hello! Welcome to QuickBank. How can I assist you today?\n"
        "User: I need to check my account balance.\n"
        "Agent: I can help with that. For security, can you verify your date of birth?\n"
        "User: It's January 10, 1990.\n"
        "Agent: Thank you. And your account number?\n"
        "User: 1234567890.\n"
        "Agent: Your current checking account balance is $4,250.37. Is there anything else I can help with?\n"
        "User: No, that's all. Thank you.\n"
        "Agent: You're welcome. Have a great day!"
    ),
    "telephony_data": {
        "recording_url": "https://bolna-recordings.s3.amazonaws.com/rec.mp3",
        "from_number": "+1987654007",
        "to_number": "+10123456789",
        "call_type": "outbound",
        "provider": "twilio",
    },
}

SYNTHFLOW_WEBHOOK = {
    "call_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "agent_goodbye",
    "duration": 95,
    "transcript": (
        "bot: Hey! This is Alex from FitZone Gym. Are you interested in our membership?\n"
        "human: Yes, I've been looking for a gym.\n"
        "bot: Great! We have a special offer right now — $29.99/month with no joining fee.\n"
        "human: That sounds good. What's included?\n"
        "bot: Full access to all equipment, group classes, sauna, and a free personal training session.\n"
        "human: When can I start?\n"
        "bot: You can start today! Would you like me to schedule your free training session?\n"
        "human: Yes, how about Saturday morning?\n"
        "bot: Saturday at 10am works. You'll get a confirmation text. See you then!\n"
        "human: Thanks, bye!\n"
        "bot: Bye! Have a great workout!"
    ),
    "collected_variables": {"name": "Mike", "phone": "+1555123456"},
    "executed_actions": [{"name": "send_confirmation", "status": "success"}],
}

GENERIC_PAYLOAD = {
    "event": "call.ended",
    "call_id": "custom-voip-001",
    "recording_url": "https://example.com/recordings/call-001.mp3",
    "transcript": (
        "Agent: Good morning, TechSupport. This is Lisa. How can I help?\n"
        "Customer: Hi Lisa, my internet has been slow all morning.\n"
        "Agent: I'm sorry to hear that. Let me check your connection. Can you confirm your account number?\n"
        "Customer: It's ACC-98765.\n"
        "Agent: Thank you. I see there's a maintenance window in your area until 2pm today. That's likely causing the slowdown.\n"
        "Customer: Oh, I wasn't aware. When will it be fixed?\n"
        "Agent: Scheduled completion is 2pm EST. Your speeds should return to normal after that.\n"
        "Customer: Okay, I'll wait. Thanks for checking.\n"
        "Agent: No problem. If it's still slow after 2pm, please call back. Have a great day!"
    ),
    "metadata": {"source": "custom-voip-system"},
}

ALL_PLATFORMS = [
    ("Vapi", VAPI_PAYLOAD),
    ("Retell", RETELL_PAYLOAD),
    ("Bland", BLAND_PAYLOAD),
    ("Bolna", BOLNA_WEBHOOK),
    ("Synthflow", SYNTHFLOW_WEBHOOK),
    ("Generic", GENERIC_PAYLOAD),
]


def print_header(text: str):
    width = 70
    print(f"\n{'='*width}")
    print(f"  {text}")
    print(f"{'='*width}")


def print_step(num: int, text: str):
    print(f"\n  [{num}] {text}")


def send_webhook(platform: str, payload: dict) -> dict | None:
    """Send a webhook and return the response."""
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

    print(f"\n  Sending {platform} webhook to {BASE_URL}/api/v1/webhooks/call-completed")
    print(f"  Payload keys: {list(payload.keys())}")

    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{BASE_URL}/api/v1/webhooks/call-completed",
                json=payload,
                headers=headers,
            )
            print(f"  Status: {resp.status_code}")
            return resp.json() if resp.status_code == 200 else {"error": resp.json()}
    except httpx.ConnectError:
        print(f"  ERROR: Cannot connect to {BASE_URL}. Is VoiceScope running?")
        print("  Start it with: uvicorn main:app --reload")
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def print_report(result: dict, platform: str):
    """Pretty-print the analysis report."""
    if "error" in result:
        print(f"\n  ERROR: {json.dumps(result['error'], indent=2)}")
        return

    pipeline = result.get("pipeline_result", {})
    report = pipeline.get("report", {})
    analysis = pipeline.get("analysis", {})

    print(f"\n  {'─'*60}")
    print(f"  PLATFORM: {result.get('platform', platform)}")
    print(f"  CALL ID:  {result.get('call_id', 'N/A')}")
    print(f"  RUN ID:   {pipeline.get('run_id', 'N/A')}")
    print(f"  {'─'*60}")

    if report:
        print(f"\n  📊 QUALITY SCORE: {report.get('quality_score', 'N/A')}/100")
        print("\n  📝 SUMMARY:")
        summary = report.get("executive_summary", "")
        if summary:
            for line in summary.split("\n")[:5]:
                print(f"     {line}")

        findings = report.get("key_findings", [])
        if findings:
            print("\n  🔍 KEY FINDINGS:")
            for f in findings[:5]:
                print(f"     • {f}")

        recs = report.get("recommendations", [])
        if recs:
            print("\n  💡 RECOMMENDATIONS:")
            for r in recs[:5]:
                print(f"     • {r}")

    if analysis:
        print("\n  📈 ANALYSIS:")
        print(f"     Intent:          {analysis.get('intent', 'N/A')}")
        print(f"     Sentiment:       {analysis.get('sentiment_arc', 'N/A')}")
        print(f"     Outcome:         {analysis.get('outcome', 'N/A')}")
        print(f"     Hallucination:   {analysis.get('hallucination_detected', 'N/A')}")
        print(f"     Escalation:      {analysis.get('escalation_signal', 'N/A')}")


def demo_single():
    """Demo: Send webhook from one platform."""
    print_header("VOICESCOPE WEBHOOK DEMO — Single Platform")
    print("\n  This demo sends a simulated webhook from Vapi to VoiceScope.")
    print("  VoiceScope auto-detects the platform and runs the analysis pipeline.")

    result = send_webhook("Vapi", VAPI_PAYLOAD)
    if result:
        print_report(result, "Vapi")


def demo_all():
    """Demo: Send webhooks from all 6 platforms."""
    print_header("VOICESCOPE WEBHOOK DEMO — All 6 Platforms")
    print("\n  Sending webhooks from: Vapi, Retell, Bland, Bolna, Synthflow, Generic")
    print("  VoiceScope auto-detects each platform from the payload structure.\n")

    results = []
    for platform, payload in ALL_PLATFORMS:
        print(f"\n{'─'*70}")
        print(f"  ▶ {platform}")
        print(f"{'─'*70}")
        result = send_webhook(platform, payload)
        if result:
            results.append((platform, result))
            print_report(result, platform)
        time.sleep(1)  # Be nice to the server

    # Summary
    print_header("SUMMARY")
    print(f"\n  {'Platform':<15} {'Call ID':<25} {'Quality':<10} {'Outcome':<15}")
    print(f"  {'─'*65}")
    for platform, result in results:
        pipeline = result.get("pipeline_result", {})
        report = pipeline.get("report", {})
        analysis = pipeline.get("analysis", {})
        call_id = result.get("call_id", "N/A")[:22]
        quality = report.get("quality_score", "N/A")
        outcome = analysis.get("outcome", "N/A")
        print(f"  {platform:<15} {call_id:<25} {str(quality):<10} {outcome:<15}")


def demo_compare():
    """Demo: Show what VoiceScope adds vs platform-native analytics."""
    print_header("VOICESCOPE vs PLATFORM-NATIVE ANALYTICS")
    print("""
  ┌─────────────────────┬──────────┬──────────┬──────────┬──────────┐
  │ Feature             │ Vapi     │ Retell   │ Bland    │VoiceScope│
  ├─────────────────────┼──────────┼──────────┼──────────┼──────────┤
  │ Hallucination Detect│ ❌ None  │ ⚠️ Ent.  │ ⚠️ Ent.  │ ✅ Every │
  │ KB Fact-Check       │ ❌       │ ❌       │ ❌       │ ✅       │
  │ Sentiment Arc       │ ❌       │ ⚠️ Binary│ ⚠️ Single│ ✅ Full  │
  │ Conversation Flow   │ ❌       │ ⚠️ Basic │ ⚠️ Path  │ ✅       │
  │ Cross-Platform      │ ❌       │ ❌       │ ❌       │ ✅       │
  │ Self-Hosted         │ ❌       │ ❌       │ ❌       │ ✅       │
  │ Multi-LLM           │ ❌       │ ❌       │ ❌       │ ✅ 5     │
  │ Plugin System       │ ❌       │ ❌       │ ❌       │ ✅       │
  │ Cost Tracking       │ ⚠️ Own   │ ⚠️ Own   │ ⚠️ Own   │ ✅ All   │
  │ Quality Score       │ ⚠️ Custom│ ⚠️ Custom│ ⚠️ Ent.  │ ✅ Built │
  └─────────────────────┴──────────┴──────────┴──────────┴──────────┘

  ⚠️ = Available but limited (Enterprise-only, binary, platform-locked)
  ✅ = Full feature available on every call
  ❌ = Not available
""")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "all":
            demo_all()
        elif cmd == "compare":
            demo_compare()
        elif cmd == "single":
            demo_single()
        else:
            print(f"Usage: {sys.argv[0]} [single|all|compare]")
    else:
        demo_single()
        print("\n\n  Try also:")
        print(f"    python {sys.argv[0]} all       # All 6 platforms")
        print(f"    python {sys.argv[0]} compare   # Feature comparison")
