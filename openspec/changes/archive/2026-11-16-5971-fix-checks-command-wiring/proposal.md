# Proposal: #5971

## Why
The command `devops roadmap step fix-checks --pull N` (#5023) repairs no check. It calls the step with no checkout and no fixer, so tier 1 never runs, the scope check reads the current folder and stops with "Failed check log is outside plan scope", and with a scope that passes the step fails with "Model repair failed". The step also writes its marks and its comment without `--confirm`, and it reads its checks and its log through attributes of a test client. The watch row of #5027 runs this command in each fix Job, so #5027 waits for this item. Closes #5971.

## What Changes
- With `--confirm`, the command refuses to run outside a runner Job (`require_runner`, as the implement job does), and gives the step the repair of a runner Job: a worktree on the head branch of the pull request, the tier 1 fixers, and the model fix of the implement repair loop.
- The worktree comes from the clone `model-clone`, or from the clone that `--source` names, and `add_worktree` with `OriginGit`, as the implement job takes over a staged branch. The push sends the new commits to the head branch with a lease on the judged head.
- Tier 1 runs only for a lint failure: `ruff check --fix` and `ruff format` on the changed Python files for a toolchain with the ruff gates, `devops docs generate` for a toolchain with the docs step, and `uv lock` when the log names `uv.lock`. It commits what changed and runs the check of each fixer again, with no model request.
- Tier 2 runs `run_fix_step` on the model of the new task `ai.tasks.fix_checks`, with the hooks and the recorded tests of the default branch, and under the new cap `roadmap.fix_checks.token_budget` (default 16,000,000 new tokens).
- Without `--confirm`, the step returns `planned` with the action that it would take, and writes nothing to GitHub, to the store or to the branch.
- When the step finds a draft that it repaired, whose checks all pass, and which `draft_readiness` calls ready, it marks the draft ready with the expected head and returns `ready`.
- The step reads its checks with `read_check_runs` and its log with `failed_log`, and no longer reads attributes of a test client.

## Capabilities
- `roadmap-fix-checks`: the command repairs a failed check end to end, honors `--confirm`, caps its model tokens, and marks a repaired draft ready.

## Impact
- Documents: ADR 0021 gets a dated fact line in its Status History: the cap of 16,000,000 new tokens for each `fix-checks` unit.
- Code: `src/devops_cli/roadmap/steps/fix_checks.py`, `src/devops_cli/roadmap/steps/fix_checks_repair.py` (new), `src/devops_cli/commands/roadmap_step_fix_checks.py`, `src/devops_cli/roadmap/implement/implement_limits.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`.
- Settings: `roadmap.fix_checks.token_budget` and `ai.tasks.fix_checks` are new. The ConfigMap template gets no `ai.tasks.fix_checks` entry in this change: the old image refuses an unknown task. Until a later change adds the entry after the release, the task takes `ai.model` (DeepSeek in the template) and the window of 128,000 tokens.

## Feasibility
- `run_fix_checks` takes `tier1_fixer`, `model_fixer`, `scope_checker` and `source`, and the command passes none (`src/devops_cli/commands/roadmap_step_fix_checks.py:55`). The probe of the issue gives `stopped` and, with the scope forced, `failed`.
- `add_worktree`, `OriginGit`, `model_clone`, `run_fix_step`, `draft_readiness` and `mark_ready` exist and the implement job uses them.

## Existing Tool Considered
- ruff (`check --fix`, `format`), `devops docs generate` and `uv lock` are the tier 1 fixers. git `worktree` and `push --force-with-lease` (through `OriginGit`) make the checkout and the push. pydantic-ai runs the model fix through `run_fix_step`. No new dependency.
