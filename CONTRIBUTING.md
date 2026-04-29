# Contributing to dj-x-supercharged

Thanks for considering a contribution. This project is small and friendly to forkers — we'd rather merge ten focused PRs than one giant one.

## Dev setup

```bash
git clone https://github.com/RenLes/dj-x-supercharged.git
cd dj-x-supercharged
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Run the offline test suite (no API keys needed):

```bash
pytest
ruff check .
mypy djx
```

## Adding a new analyzer backend

The most common contribution. Subclass `BaseAnalyzer`:

```python
# djx/analyzer/myllm.py
from djx.analyzer.base import BaseAnalyzer
from djx.analyzer.schema import TweetAnalysis

class MyLLMAnalyzer(BaseAnalyzer):
    async def analyze(self, tweet_text: str) -> TweetAnalysis:
        # call your LLM, parse JSON, return TweetAnalysis(...)
        ...
```

Then verify against the contract:

```python
# tests/test_myllm.py
import asyncio
from tests.test_base_analyzer import analyzer_contract
from djx.analyzer.myllm import MyLLMAnalyzer

def test_contract():
    asyncio.run(analyzer_contract(MyLLMAnalyzer()))
```

Optionally export it from `djx/__init__.py` so users can `from djx import MyLLMAnalyzer`.

## PR checklist

- [ ] Tests pass: `pytest`
- [ ] Lint clean: `ruff check .`
- [ ] Types clean: `mypy djx` (errors that already existed are fine; don't introduce new ones)
- [ ] Updated `CHANGELOG.md` under `## [Unreleased]`
- [ ] No live-API calls in tests — use fixtures or `respx`
- [ ] No secrets in commits (pre-commit + gitleaks should catch this)

## Commit style

Imperative, short. Example:
```
Add OpenAI analyzer backend
Fix X 429 backoff to honor x-rate-limit-reset
```

## Reporting bugs

Open an issue using the **Bug report** template. Include:
- Python version
- The exact `djx` command run
- Redacted error output (no tokens, please)

## Code of conduct

By contributing you agree to abide by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
