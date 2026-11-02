"""Opt-in synthetic staging boundaries. Normal deployments keep existing behavior."""

import os
from pathlib import Path


def demo_enabled() -> bool:
    return os.getenv('STAGING_DEMO_ONLY') == 'true'


def public_demo_enabled() -> bool:
    return demo_enabled() and os.getenv('PUBLIC_SYNTHETIC_DEMO') == 'true'


def require_live_services() -> None:
    if demo_enabled():
        raise RuntimeError('Synthetic demo mode disables live providers and recording downloads')


def validate_demo_environment() -> list[str]:
    if os.getenv('DATABASE_URL'):
        raise ValueError('Synthetic staging must not connect to an external database')
    root = Path(os.getenv('DATA_DIR', ''))
    if not root.is_absolute() or root.resolve() == Path('/'):
        raise ValueError('Synthetic staging requires its own absolute DATA_DIR')
    root = root.resolve()
    for name in ['MONITORING_DB_PATH', 'COST_DB_PATH', 'POLICY_DB_PATH', 'KNOWLEDGE_DB_PATH',
                 'QA_DB_PATH', 'EXTRACTIONS_DB_PATH', 'OPTIMIZER_DB_PATH', 'STT_REVIEW_DIR',
                 'CHROMA_PERSIST_DIR']:
        if os.getenv(name) and not Path(os.environ[name]).resolve().is_relative_to(root):
            raise ValueError('Synthetic staging storage must stay inside DATA_DIR')
    for name in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY', 'GROQ_API_KEY',
                 'MISTRAL_API_KEY', 'DEEPGRAM_API_KEY', 'BOLNA_API_KEY', 'OPENCODE_GO_API_KEY',
                 'OPENROUTER_API_KEY']:
        if os.getenv(name):
            raise ValueError('Synthetic staging must not contain live provider credentials')
    keys = [key.strip() for key in os.getenv('VALID_API_KEYS', '').split(',') if key.strip()]
    if not keys or any(len(key) < 24 for key in keys):
        raise ValueError('Synthetic staging needs a separate API key of at least 24 characters')
    return keys
