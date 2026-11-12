# Proposal

## Why

The owner rule of 2026-11-11 says that each inner time limit ends before the limit around it, so that the inner limit exits with a diagnostic. The pre-push hooks run inside the shell tool of an agent, whose default limit is 120 s, and they have no limit of their own (#4775).

coreutils `timeout` is the standard tool for such a limit, but `devops ci` did not let it work. `timeout` ends a command with SIGTERM. The gate run of `devops ci` took no stop signal, so the default handler ended Python at once. Each row runs in a session of its own (#1669), so each row kept running, and no line named the row. `devops ci test` already stops its run on a stop signal (`ci-test-stop`); the gate run did not.

## What Changes

- The gate run of `devops ci` takes Ctrl-C, SIGTERM and SIGHUP through the helper of `devops ci test`. A stop signal cancels the run. Each row that still runs stops with its whole process group (SIGINT, SIGTERM, then SIGKILL), and gets the line `✗ fail <title> (stopped after <time>)`. The run exits as cancelled, with exit status 130.
- The two `devops ci` hooks of the pre-push stage run under coreutils `timeout`: 40 s for `lint,format` and 30 s for `actionlint,zizmor`. `branch-current` keeps its fetch limit of 20 s.
- A structural test reads `.pre-commit-config.yaml`. It fails when a pre-push hook has no `timeout` limit, or when the limits plus 25 s for the rest of the push are not less than 120 s.
- The runner image lists `timeout` (coreutils of the base image) as a program of the three pre-push hooks.

## Capabilities

### New Capabilities

- `ci-gate-stop`: A stop signal stops each running row of the gate, The pre-push hooks end before the agent shell limit.

## Impact

- Code: `src/devops_cli/commands/ci.py`, `src/devops_cli/roadmap/runner_tools.py`, `.pre-commit-config.yaml`
- Tests: `tests/commands/test_ci.py`, `tests/invariants/test_workflow_contracts.py`, `tests/invariants/test_runner_hooks.py`, `tests/commands/test_instruction_generator.py`
- Documents: `docs/SDLC.md`
- `devops ai agents` now names the two check hooks with their `timeout` prefix.
- A push whose checks take more than 40 s (or 30 s for the workflow checks) fails with the names of the rows. Under a load average of 20 to 25 on 16 CPUs, the checks took 12 s to 23 s.
- Every supervisor that sends a stop signal (`timeout`, a person, the agent shell) now stops the rows of the gate. Before, it left them running.

## Feasibility

- Reproduction at `origin/main` 87ae9eef: `timeout 15 uv run devops ci --check --only startup-imports,swallowed-failures` returned 124, and `ps` showed the two rows and their `python -X importtime` children still running. One row still ran 69 s after the limit.
- With this change, the same command returned 124 after 20 s, printed `✗ fail startup imports ... (stopped after 9.27s)` and `✗ fail swallowed failures ... (stopped after 9.31s)`, and `ps` showed no process of the run.
- coreutils `timeout` (default mode) sends the signal to its own process group, which holds `uv` and `devops`. uv 0.13.6 also forwards SIGTERM to its child: a test with `timeout --foreground 3 uv run python ...` showed that the child got SIGTERM.
- pre-commit has no time limit for a hook, so the limit goes into the `entry`, as `branch-current` already does for its fetch.
- The `ci.yml` part of the issue is done: `Static Analysis` now has a job limit of 6 minutes and a step limit of 3 minutes, and `tests/invariants/test_workflow_contracts.py` already fails when a step limit is not under its job limit.

## Existing Tool Considered

coreutils `timeout`, which this change uses. The issue proposed `devops ci --timeout` and a setting `ci.check_timeout_seconds` because `timeout` left the rows running. That was a defect of `devops ci`, not of `timeout`, so this change repairs the defect and adds no option and no setting.
