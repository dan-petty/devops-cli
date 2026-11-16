# Proposal: #5023

## Why
Fix rounds run only inside the runner Job, before the ready mark. When the Job ends, no job fixes the pull request. The classes test, lint, and types have the action REPAIR, but no job takes it. A plan draft with a failing check stays a draft (#3387). Each fix round uses a model, also for a lint or lock failure that a tool can fix. Closes #5023.

## What Changes
- Add `src/devops_cli/roadmap/steps/fix_checks.py` providing `run_fix_checks`.
- Add command `devops roadmap step fix-checks --pull N` in `src/devops_cli/commands/roadmap_step_fix_checks.py` and register it in `roadmap_step.py`.
- Classify failed check log with `classify_failure`.
- Tier 1 (deterministic, 0 model calls): run `ruff check --fix` and `ruff format` on changed paths for lint failures, `devops docs generate` for doc failures, or `uv lock` for lockfile failures.
- Tier 2 (model): run `run_fix_step`, only when the log names a path within the repair scope.
- Enforce bounds: bot pull requests only, stop on `owner/*` labels, skip if head moved, soft cap 3 rounds (extendable while error count falls), hard cap 5 rounds, at most 3 heads per pull request.
- Record keys `fix_checks.key` (`<head>:<check>`), `fix_checks.rounds`, `fix_checks.errors`, `fix_checks.result`.
- Update runner Job repair loop to record `fix_checks.*` keys.

## Capabilities
- Automate tier 1 fixes for lint, docs, and lockfile failures with 0 model requests.
- Automate tier 2 model fixes for failed checks within plan scope.
- Settle failed checks on both delivery drafts and stage plan drafts.

## Impact
- Reduces token usage by resolving deterministic check failures without model calls.
- Recovers stalled draft pull requests automatically.

## Feasibility
- Confirmed against existing implementations of `run_fix_step`, `failed_log`, `classify_failure`, and `repair_scope`.

## Existing Tool Considered
- ruff (`check --fix`, `format`), `devops docs generate`, and `uv lock` fix tier 1 failures with 0 model calls.
