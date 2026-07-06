# Contributing to VoiceScope

Thanks for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/ShivamChavan01/voicescope
cd voicescope
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v --cov=.
```

## Code Style

- Format: `ruff format .`
- Lint: `ruff check .`
- Type check: `mypy . --ignore-missing-imports`

## Adding a Provider

1. Create `llm_providers/your_provider.py`
2. Implement `LLMProvider` base class
3. Register in `llm_providers/registry.py`
4. Add tests in `tests/test_providers.py`

## Pull Requests

1. Fork the repo
2. Create a feature branch
3. Add tests for new features
4. Ensure CI passes
5. Submit a PR
