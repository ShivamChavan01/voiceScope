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

## Adding a Validation Layer

1. Create `core/your_layer.py`
2. Implement the check function
3. Wire it into `core/harness.py`
4. Add to `_compute_truth_score()` weights
5. Add tests in `tests/test_harness.py`

## Pull Requests

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Add tests for new features
4. Ensure CI passes (`ruff check . && mypy . --ignore-missing-imports && pytest`)
5. Submit a PR with a clear description

## Reporting Bugs

Open a GitHub issue with:
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
- Relevant logs/error messages

## Feature Requests

Open a GitHub issue describing:
- The problem you're trying to solve
- Your proposed solution
- Alternatives you considered
