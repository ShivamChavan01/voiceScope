#!/usr/bin/env python3
"""
VoiceScope CLI — analyze voice AI calls from the terminal.

Usage:
    voicescope analyze <audio_file>     Analyze a call recording
    voicescope serve                    Start the API server
    voicescope init                     Interactive setup
    voicescope status                   Show system status
"""

import sys
import os
import asyncio
import json
import signal
from pathlib import Path

# Bootstrap: set defaults before any imports
os.environ.setdefault("DATA_DIR", ".voicescope")
os.environ.setdefault("VALID_API_KEYS", "vs-local-key")


def _ensure_data_dir():
    data_dir = Path(os.environ.get("DATA_DIR", ".voicescope"))
    data_dir.mkdir(parents=True, exist_ok=True)
    env_file = Path(".env")
    if not env_file.exists():
        env_file.write_text(
            "# VoiceScope — run `voicescope init` for interactive setup\n"
            "VALID_API_KEYS=vs-local-key\n"
            "LLM_PROVIDER=groq\n"
            "DATA_DIR=.voicescope\n"
        )


def _print_banner():
    print("\033[1;36m")
    print("     __      __  ______   ______   ___  ____ ")
    print(r"     \ \    / / / ___\ \ / /___ \ / _ \/ ___|")
    print(r"      \ \/\/ / | |    \ V /  __) | | | \___ \ ")
    print(r"       \_/\_/  |_|     |_| |____/|_| |_|\___/ ")
    print("\033[0m")
    print("  \033[2mcatch hallucinations before your users do\033[0m\n")


def _format_report(result: dict) -> str:
    lines = []
    harness = result.get("harness", {})
    truth = harness.get("truth_score", 0)
    confidence = harness.get("confidence", "unknown")

    # Color based on truth score
    if truth >= 0.8:
        color, label = "\033[92m", "PASS"
    elif truth >= 0.5:
        color, label = "\033[93m", "WARN"
    else:
        color, label = "\033[91m", "FAIL"
    reset = "\033[0m"

    lines.append(f"{'─' * 60}")
    lines.append(f"  {color}Truth Score: {truth:.2f}  [{label}]{reset}  Confidence: {confidence}")
    lines.append(f"{'─' * 60}")

    # Transcript preview
    transcript = result.get("raw_transcript", "")
    if transcript:
        preview = transcript[:300] + ("..." if len(transcript) > 300 else "")
        lines.append(f"\n  Transcript:")
        lines.append(f"  {preview}")

    # Analysis
    intent = result.get("intent", "")
    sentiment = result.get("sentiment_arc", "")
    outcome = result.get("outcome", "")
    hallucination = result.get("hallucination_detected", False)

    if intent:
        lines.append(f"\n  Intent:      {intent}")
    if sentiment:
        lines.append(f"  Sentiment:   {sentiment}")
    if outcome:
        lines.append(f"  Outcome:     {outcome}")
    if hallucination:
        evidence = result.get("hallucination_evidence", "")
        lines.append(f"  \033[91mHallucination Detected: {evidence or 'see details'}{reset}")

    # Harness layer scores
    layer_scores = harness.get("layer_scores", {})
    if layer_scores:
        lines.append(f"\n  Harness Layers:")
        for layer, score in layer_scores.items():
            bar_len = int(score * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"    {layer:<30} {bar} {score:.2f}")

    # Errors
    errors = result.get("errors", [])
    if errors:
        lines.append(f"\n  \033[93mWarnings:{reset}")
        for err in errors[:5]:
            lines.append(f"    ⚠ {err}")

    # Cost
    provider = result.get("provider", {})
    if provider.get("cost_usd"):
        lines.append(f"\n  Cost: ${provider['cost_usd']:.4f} ({provider.get('model', 'unknown')})")

    lines.append(f"\n{'─' * 60}")
    return "\n".join(lines)


async def _cmd_analyze(audio_path: str, json_output: bool = False):
    _print_banner()

    path = Path(audio_path)
    if not path.exists():
        print(f"\033[91m  Error: {audio_path} not found\033[0m")
        sys.exit(1)

    file_size = path.stat().st_size
    if file_size > 25 * 1024 * 1024:
        print(f"\033[91m  Error: File too large ({file_size / 1024 / 1024:.1f}MB, max 25MB)\033[0m")
        sys.exit(1)

    print(f"  Analyzing: {path.name} ({file_size / 1024:.0f}KB)")
    print(f"  Provider:  {os.environ.get('LLM_PROVIDER', 'openai')}")
    print(f"  STT:       {os.environ.get('STT_PROVIDER', 'deepgram')}\n")

    # Import and run pipeline
    from core.pipeline import VoiceScopePipeline

    pipeline = VoiceScopePipeline()

    print("  \033[2m⏳ Transcribing...\033[0m", end="", flush=True)
    result = await pipeline.run(path.read_bytes(), path.name)
    print("\r" + " " * 40 + "\r", end="")

    if json_output:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(_format_report(result))


async def _cmd_serve(host: str = "0.0.0.0", port: int = 8000):
    _print_banner()
    print(f"  Starting server on http://{host}:{port}")
    print(f"  API docs:  http://localhost:{port}/docs")
    print(f"  Health:    http://localhost:{port}/api/v1/health\n")

    import uvicorn
    config = uvicorn.Config("main:app", host=host, port=port, reload=True)
    server = uvicorn.Server(config)
    await server.serve()


def _cmd_init():
    _print_banner()
    print("  Let's set up VoiceScope.\n")

    env_path = Path(".env")
    env_lines = []

    # LLM Provider
    print("  LLM Provider:")
    print("    1) Groq (free tier — recommended)")
    print("    2) OpenAI")
    print("    3) Anthropic")
    print("    4) Gemini")
    choice = input("\n  Choice [1]: ").strip() or "1"
    providers = {"1": "groq", "2": "openai", "3": "anthropic", "4": "gemini"}
    provider = providers.get(choice, "groq")
    env_lines.append(f"LLM_PROVIDER={provider}")

    # API Key
    key_name = f"{provider.upper()}_API_KEY"
    api_key = input(f"\n  {key_name} (press Enter to skip): ").strip()
    if api_key:
        env_lines.append(f"{key_name}={api_key}")

    # STT Provider
    print("\n  STT Provider:")
    print("    1) Deepgram (recommended)")
    print("    2) Whisper (OpenAI)")
    choice = input("\n  Choice [1]: ").strip() or "1"
    stt = "deepgram" if choice == "1" else "whisper"
    env_lines.append(f"STT_PROVIDER={stt}")

    if stt == "deepgram":
        stt_key = input("\n  DEEPGRAM_API_KEY (press Enter to skip): ").strip()
        if stt_key:
            env_lines.append(f"DEEPGRAM_API_KEY={stt_key}")

    # API key
    import secrets
    api_key = f"vs-{secrets.token_hex(16)}"
    env_lines.append(f"VALID_API_KEYS={api_key}")
    env_lines.append("DATA_DIR=.voicescope")

    # Write
    env_path.write_text("\n".join(env_lines) + "\n")
    print(f"\n  \033[92m✓ Config saved to .env\033[0m")
    print(f"  \033[2mAPI key: {api_key}\033[0m")
    print(f"\n  Next steps:")
    print(f"    voicescope analyze test-audio/tadhack/day-21/3529f7fa-4f73-4660-86c4-95ffc0473043.mp3")
    print(f"    voicescope serve")


def _cmd_status():
    _print_banner()

    checks = []

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("Python", py_ver, sys.version_info >= (3, 11)))

    # Dependencies
    deps = ["fastapi", "openai", "chromadb", "asyncpg"]
    for dep in deps:
        try:
            __import__(dep)
            checks.append((dep, "installed", True))
        except ImportError:
            checks.append((dep, "missing", False))

    # API keys
    providers = {
        "OPENAI_API_KEY": "OpenAI",
        "ANTHROPIC_API_KEY": "Anthropic",
        "GROQ_API_KEY": "Groq",
        "DEEPGRAM_API_KEY": "Deepgram",
    }
    for env_key, name in providers.items():
        val = os.environ.get(env_key, "")
        if val:
            checks.append((name, f"set ({val[:8]}...)", True))
        else:
            checks.append((name, "not set", False))

    # Database
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        checks.append(("PostgreSQL", "configured", True))
    else:
        checks.append(("PostgreSQL", "not set (using SQLite)", True))

    # Print
    for name, status, ok in checks:
        icon = "\033[92m✓\033[0m" if ok else "\033[91m✗\033[0m"
        print(f"  {icon} {name:<15} {status}")
    print()


def main():
    if len(sys.argv) < 2:
        _print_banner()
        print("  Usage:")
        print("    voicescope analyze <file>   Analyze a call recording")
        print("    voicescope serve            Start the API server")
        print("    voicescope init             Interactive setup")
        print("    voicescope status           Show system status")
        print()
        return

    _ensure_data_dir()

    cmd = sys.argv[1]

    if cmd == "analyze":
        if len(sys.argv) < 3:
            print("\033[91m  Usage: voicescope analyze <audio_file> [--json]\033[0m")
            sys.exit(1)
        json_out = "--json" in sys.argv
        asyncio.run(_cmd_analyze(sys.argv[2], json_output=json_out))

    elif cmd == "serve":
        host = "0.0.0.0"
        port = 8000
        for arg in sys.argv[2:]:
            if arg.startswith("--port"):
                port = int(arg.split("=")[1]) if "=" in arg else int(sys.argv[sys.argv.index(arg) + 1])
            if arg.startswith("--host"):
                host = arg.split("=")[1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1]
        asyncio.run(_cmd_serve(host, port))

    elif cmd == "init":
        _cmd_init()

    elif cmd == "status":
        _cmd_status()

    elif cmd in ("--help", "-h", "help"):
        _print_banner()
        print("  voicescope analyze <file>   Analyze a call recording")
        print("  voicescope serve            Start the API server")
        print("  voicescope init             Interactive setup")
        print("  voicescope status           Show system status")
        print()

    else:
        print(f"\033[91m  Unknown command: {cmd}\033[0m")
        print("  Run 'voicescope --help' for usage")
        sys.exit(1)


if __name__ == "__main__":
    main()
