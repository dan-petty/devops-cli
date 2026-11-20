# Proposal: #6539

## Why

The implement Job clears the dumpable flag of its process and adopts the orphans of a step before its first step (`apply_implement`, #2667). The fix-checks Job runs a model step in the same runner pod, but it does neither. Closes #6539.

## What Changes

With `--confirm` in a runner Job, `devops roadmap step fix-checks` calls `deny_environment_reads()` and `adopt_orphans()` of `src/devops_cli/core/process_hardening.py` after `require_runner` and before the step runs.

## Capabilities

- `roadmap-fix-checks`: ADDED requirement 'The Job makes its process unreadable before the repair'.

## Impact

The fix-checks Job gets the same process guards as the implement Job. A kernel that refuses either call stops the Job before the step, with the error of `process_hardening`.

## Feasibility

- `src/devops_cli/roadmap/implement/implement_run.py:2470-2472` calls `require_runner`, `deny_environment_reads` and `adopt_orphans` in this order. `src/devops_cli/commands/roadmap_step_fix_checks.py` called only `require_runner` before `job_repair` and `run_fix_checks`.
- The new command test fails before the change (`['runner', 'step']`) and passes after it.

## Existing Tool Considered

The change reuses the two functions of `process_hardening` that the implement Job uses. It adds no code beyond the two calls.
