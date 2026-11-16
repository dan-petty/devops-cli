# Design

## Decisions
- Expose `run_fix_checks` in `src/devops_cli/roadmap/steps/fix_checks.py`.
- Register `fix-checks` subcommand in `src/devops_cli/commands/roadmap_step.py`.
- Classify failures using `classify_failure` and `FailureEvidence`.
- Tier 1 handlers:
  - Lint: run `ruff check --fix` and `ruff format` on changed files.
  - Docs: run `devops docs generate`.
  - Lock: run `uv lock`.
  If the check passes afterwards locally, commit and push with `--force-with-lease`.
- Tier 2 handlers:
  - If log does not name a file in `repair_scope`, stop with 0 model calls.
  - If log names a file in `repair_scope`, run `run_fix_step`.
- Enforce caps:
  - Soft cap: 3 rounds (from settings).
  - One more round allowed if error count decreased (`current_errors < prev_errors`).
  - Hard cap: 5 rounds.
  - Head limit: at most 3 distinct heads per pull request.
- Record keys:
  - `fix_checks.key`: `<head>:<check>`
  - `fix_checks.rounds`: round count
  - `fix_checks.errors`: error count
  - `fix_checks.result`: outcome string

## Rejected alternatives
- Running a model call on every lint or lock error: rejected because standard formatters and lock tools fix these deterministically at 0 token cost.
- Unlimited repair rounds: rejected to avoid infinite repair loops on unresolvable CI checks.
