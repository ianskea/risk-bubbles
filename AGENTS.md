# Repository Guidelines

## Project Structure & Module Roles
- `enhanced_risk_analyzer.py`: multi-factor engine with valuation, momentum, volatility, and volume components.
- `run_validated_analysis.py`: CLI entry for validation/analysis modes; option 1 runs the validation suite, option 3 runs a quick single-asset check.
- `enhanced_main.py`: batch portfolio reporting; writes reports to `output/` and charts to `output/charts/{ticker}_comprehensive.png`.
- `main.py` and `risk_analyzer.py`: original baseline flow kept for comparison.
- Support files: `model_validation.py` (stat tests), `perf_test.py` (micro-benchmark), `investment_planner.py`/`system_audit.py` (ancillary tooling), `requirements.txt`, `.env.example` (copy to `.env`), and generated assets in `output/`.

## Setup & Key Commands
- Install deps: `pip install -r requirements.txt` (use the provided `venv/` or create your own virtualenv).
- Quick validation: `python run_validated_analysis.py` → pick option 3 for a fast single-ticker check.
- Full validation suite: `python run_validated_analysis.py` → pick option 1 to evaluate multiple assets.
- Portfolio report: `python enhanced_main.py` to refresh text reports and `[TICKER]_risk_bubble.png` charts in `output/`.
- Legacy baseline: `python main.py` for the original pipeline; `python perf_test.py` to sanity-check regression performance.

## Coding Style & Naming
- Follow PEP 8 with 4-space indentation; keep modules lowercase and functions/variables in `snake_case`.
- Use type hints and docstrings (matching existing patterns) for public functions; prefer clear pandas/numpy operations over ad-hoc loops.
- Keep logging/prints purposeful and actionable; avoid committing exploratory code or notebook artifacts.

## Testing & Validation
- No formal unit test suite yet; rely on `run_validated_analysis.py` option 1 (multi-asset) or option 3 (single-asset) as regression checks.
- When touching scoring logic, confirm generated reports in `output/` (text files and charts) and spot-check that risk scores and percentiles change as expected.
- Note any data fetch constraints or yfinance quirks observed during runs in your PR description.

## Commit & Pull Request Guidelines
- Write concise, imperative commit subjects (e.g., `Refine validation scoring`, `Add DeepSeek config guard`).
- PRs should summarize intent, list key code paths touched, and attach sample output paths (e.g., `output/BTC-USD_risk_bubble.png`) or CLI snippets.
- Link related issues, call out behavioral changes, and mention any follow-up work needed (data, tuning, infra).

## Security & Config
- Never commit secrets; copy `.env.example` to `.env` locally and keep keys (e.g., `DEEPSEEK_API_KEY`) out of version control.
- Generated artifacts can be large—only commit those necessary for reviewers to validate outputs.
