# Proposal: #5983

## Why
The step `fix-checks` (#5971) can repair and push a bot pull request. A review after the merge found gaps that matter as soon as #5027 starts the step as a Job. The step does not read the record of a live implement Job. It runs the same failed round again on each call, with a model repair of up to 16,000,000 tokens and a new infrastructure comment each time. The cap of heads stops the call on the head that the third repair pushed, before the ready path. Tier 1 starts only for the class lint, so a stale `uv.lock` in the check `Tests` never gets `uv lock`. No test moves the head between the judgment and the push, and no test covers the branch and SHA guard of the checkout. Closes #5983.

## What Changes
- The step returns `skipped` for an item whose record names an implement Job with no recorded state (`job_holds`), as `fix-plan` leaves such an item out.
- The step returns `skipped`, before it reads the log, when `fix_checks.key` is `<head>:<check>` of the first failed check and `fix_checks.result` is `failed`, `stopped` or `wait`.
- The cap of heads moves after the ready path: it stops only a head with a failed check.
- Tier 1 starts on a lint failure, on a docs failure or on a lockfile failure in the log, whatever the class of the check. A failure that tier 1 has a fixer for gets no infrastructure wait.
- New tests: a push whose lease breaks, and the branch and SHA guard of the checkout.

## Capabilities
- `roadmap-fix-checks`: two new requirements (the live Job, no repeated round) and changes to the bounds, tier 1, the infrastructure wait and the runner Job scenarios.

## Impact
- Code: `src/devops_cli/roadmap/steps/fix_checks.py`, `src/devops_cli/roadmap/steps/fix_checks_repair.py`.
- Tests: `tests/roadmap/steps/test_roadmap_step_fix_checks.py`, `tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`.
- No setting, no command option and no record key changes. ADR 0021 section 8 stays true: its tier 1 row names the same fixers, and the idempotency key `<pr>:<head>:<check>` gets the same rule in the step.

## Feasibility
- `_check_preconditions` reads only the owner labels and `len(heads) > 3` (`src/devops_cli/roadmap/steps/fix_checks.py:236-285` on 0.165.0). `fix_checks.key` has writers in `fix_checks.py:339` and `implement_run.py:1864`, and no reader.
- The record keeps `implement.job` after the Job ends, and the Service writes `implement.job_state` then (`implement_submit.py:367`). `job_holds` (`status_sync.py:170`) reads both, so the guard does not stop each implement draft whose Job ended.
- uv 0.13.7 prints "The lockfile at `uv.lock` needs to be updated" for `uv sync --locked` and `uv lock --check` (probe in a scratch project). `setup-toolchain` runs `uv sync --locked` in each CI job, and its log names `uv.lock` in the inputs of `setup-uv`, so the old trigger "the log names `uv.lock`" is too wide for a check of any class.

## Existing Tool Considered
- uv (`uv lock`, `uv lock --check`), ruff and `devops docs generate` stay the fixers; the lease of the push stays the lease of git. The guards read the existing record keys. No new dependency.
