## Why

`devops ai chat --persona` defaults to a static persona (`architect`), no caller selects a persona lens from evidence, and neither spans, review profiles, nor Prometheus counters record which lens or selection rule ran (Closes #4830, Refs #4780).

## What Changes

- Add ordered rule table `src/devops_cli/ai/personas/lens.toml` and `select_lens(evidence) -> LensChoice` in `src/devops_cli/ai/personas/lens.py` evaluating explicit flags, fixed step roles, finding producers/CWEs, `pathspec` path globs, and `type/*`/`scope/*` labels first-match-wins (returning no lens when nothing matches).
- Record `lens` (default `"none"`) and `lens_rule` (default `""`) on `ReviewProfile` (`profile.json`) alongside `prompt_digest`, record span attributes `ai.lens` and `ai.lens.rule`, and compute `chat_prompt` digests via `run_store.digest`.
- Declare bounded counter `AI_LENS_TOTAL` (`devops_cli_ai_lens_total{caller,lens,source}`, <= 84 series) in `src/devops_cli/telemetry/instruments.py` and regenerate `docs/TELEMETRY.md`.
- Update `devops ai chat --persona` to default to `None` (resolved to `architect` with `source="default"`), record `source="flag"` for explicit flags, and support `--persona auto` to choose the lens from working-tree changes (`source="rule"`).

## Capabilities

### Modified Capabilities

- `ai-chat-personas`: Select chat personas via `--persona auto`, distinguish explicit `--persona` flags (`source="flag"`) from default `architect` (`source="default"`), and emit `ai.lens`/`devops_cli_ai_lens_total`.
- `ai-review-profile`: Record `lens` and `lens_rule` fields in `ReviewProfile` / `profile.json` and define `lens.toml` / `select_lens` evidence matching.

## Impact

- `src/devops_cli/ai/personas/lens.toml` and `src/devops_cli/ai/personas/lens.py`
- `src/devops_cli/ai/personas/__init__.py`
- `src/devops_cli/ai/review/profile.py`
- `src/devops_cli/telemetry/instruments.py` and `docs/TELEMETRY.md`
- `src/devops_cli/commands/ai.py`, `docs/commands/ai.md`, `docs/CLI_REFERENCE.md`
- `tests/ai/personas/test_lens.py`, `tests/ai/review/test_review_profile.py`, `tests/commands/test_ai_cmd.py`, `tests/telemetry/test_telemetry_instruments.py`

## Feasibility

- `src/devops_cli/ai/personas/__init__.py` defines the fixed six-member `Persona` enum, `PERSONAS`, and `review_prompt_digest()`, `src/devops_cli/ai/run_store.py` provides `digest()`, `src/devops_cli/telemetry/instruments.py` declares bounded counters checked by `tests/telemetry/test_telemetry_instruments.py`, and `pathspec` is already a project dependency (`pyproject.toml`).
- `devops ai chat --persona auto` inspects working-tree paths with `git` without blocking CLI startup (`commands/ai.py` keeps imports lazy).

## Existing Tool Considered

Uses the project's existing `pathspec` dependency (MPL-2.0, `https://pypi.org/project/pathspec`) and standard-library `tomllib`/`fnmatch` with a small TOML rule table (`lens.toml`), reusing `PERSONAS`, `ReviewProfiler`, `run_store.digest`, and `telemetry.instruments` rather than introducing an external rule engine. Estimated build cost: ~25,000 tokens and ~1 hour.
