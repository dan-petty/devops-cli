# Tasks

## 1. Selector, Profile & Telemetry

- [x] 1.1 Write failing tests for `lens.toml` rule order/uniqueness, every matcher row, span/profile recording, `AI_LENS_TOTAL` bounded series, and `devops ai chat --persona auto` / default / explicit sources
  - Verification: `$ uv run pytest -n 0 tests/ai/personas/test_lens.py tests/ai/review/test_review_profile.py tests/commands/test_ai_cmd.py tests/telemetry/test_telemetry_instruments.py`
- [x] 1.2 Add `src/devops_cli/ai/personas/lens.toml` and `lens.py`, update `profile.py`, `telemetry/instruments.py`, `commands/ai.py`, and `tests/conftest.py` cache reset
  - Verification: `$ uv run pytest -n 0 tests/ai/personas/test_lens.py tests/ai/review/test_review_profile.py tests/commands/test_ai_cmd.py tests/telemetry/test_telemetry_instruments.py`

## 2. Docs & CI Gate

- [x] 2.1 Regenerate `docs/TELEMETRY.md`, `docs/commands/ai.md`, and `docs/CLI_REFERENCE.md` and pass `devops docs check`, `devops openspec check`, and `devops ci --check`
  - Verification: `$ uv run devops docs generate && uv run devops docs check && uv run devops openspec check && uv run devops ci --check`
