# Design: #4076 Rebase staged branch onto main before implement

## Context
When an implementation runner starts on a staged branch, the branch can lag behind `origin/main`. The implement job already fetches the default branch and rebases before the first step and before the push, stopping on conflicts. For manual debugging in a runner, a person needs an escape hatch to run without rebasing onto `main`.

## Architecture & Implementation Details

### 1. CLI Option
In `src/devops_cli/commands/roadmap.py`:
- Add `rebase: Annotated[bool, typer.Option("--rebase/--no-rebase", help=HELP.roadmap.implement_rebase)] = True` to `implement_cmd`.
- Pass `rebase=rebase` into `_implement_job`.
- If `--group` is given with `--no-rebase`, refuse with `MESSAGES.roadmap.implement_step_job_options`.

### 2. Runner-only Enforcement
In `src/devops_cli/roadmap/implement/implement_outside.py`:
- Update `runner_only_options(*, source: Path | None, filters: Sequence[str] | None, limit: int, rebase: bool = True) -> list[str]` to check `"--no-rebase": not rebase`.
- Workstation runs with `--confirm` and `--no-rebase` are refused with `refusal(target, options=options)`.
- Dry runs outside a runner ignore `--no-rebase` when rendering the runner job plan, matching existing behavior for `--source`, `--filter`, and `--limit`.

### 3. Execution Pipeline
In `src/devops_cli/roadmap/implement/implement_run.py`:
- Accept `rebase: bool = True` in `apply_implement`, `_implement_item`, and `_ItemRun`.
- In `_sync()`: return immediately without fetching `origin/<default>` or rebasing when `not self.rebase`.
- In `_rebased_copy()`: return `self._head()` immediately when `not self.rebase`.

### 4. Dry Run & Request Plan
In `src/devops_cli/roadmap/implement/implement.py` and `src/devops_cli/roadmap/request_plan.py`:
- Pass `rebase: bool = True` through `dry_run_implement` and `implement_requests`.
- In `implement_requests`, include `git("rebase", tree, "rebase", "origin/main")` in `writes` only when `rebase` is true.

## Decisions & Alternatives
- **CLI flag vs setting**: Added CLI flag `--rebase/--no-rebase`. Unattended runs via CronJob run with defaults, ensuring automated runs always rebase.
- **Outside runner behavior**: Refuse `--no-rebase` outside runner when `--confirm` is given, directing the user to `devops k8s run-job --template runner`.
