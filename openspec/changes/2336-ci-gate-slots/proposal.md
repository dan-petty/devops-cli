# Proposal

## Why

Issue #2336: several agents work on this repository at the same time, and each runs `devops ci` in its own worktree. Nothing limits how many gates share the host, and the pytest of each gate starts one worker for each CPU. ADR 0014 records the result: "Nothing limits how many runs share the host, and the pytest of each run uses every CPU. The load average reached 88."

The CI cache of the host holds 399 passing runs. The `test` check has a median of 243 s and a maximum of 1435 s. The `security` check has a median of 98 s and a maximum of 1688 s. The `typecheck` check has a median of 57 s and a maximum of 856 s. A gate takes 2.5 minutes on a quiet host and 7 to 15 minutes under load (#1752). Timed tests then fail (#2069, #2092) and the run starts again. The container also has a `pids.max` of 2048, so a burst of gates can fail to fork. A check that averages more than 5 minutes is a P0 bug (AGENTS.md, rule 5).

## What Changes

- `devops ci` takes a host-wide gate slot before it starts a CPU-heavy check, and gives the slot back when it ends. When every slot is held, it waits and names the worktree and process that hold them.
- A check is heavy when its p90 in the CI cache is above 200 s: `test`, `security` and `typecheck`. `CheckSpec` gets a `heavy` flag. A run needs a slot only when it selects a heavy check, so the pre-push hook (`--only lint,format,actionlint,zizmor`) never waits.
- `devops ci test` and `devops ci coverage` take a slot too, because they start the same workers.
- A dry run and a cached verdict take no slot. The time a run waits for a slot is not part of the elapsed time of the gate, so the over-budget warning does not count it.
- The setting `ci.gate_slots` sets the number of slots. Without it, the number is `max(1, cpu_count // 8)`: 2 on a 16-CPU host and 1 on a 4-CPU GitHub runner, where a single job never waits.
- Each run records the time it waited as the metric `ci.gate_slot_wait_seconds`, so a person can see the effect of the limit.
- `filelock` becomes a direct dependency. It is already in `uv.lock` as a dependency of `tldextract`.
- The change adds the capability `ci-gate-admission`. It does not change `ci-test-stop`, which covers the pytest run only. A run that waits for a slot has no child yet, so the new capability states that a stop signal ends the wait and leaves no slot held.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `ci-gate-admission`: how `devops ci` limits the CPU-heavy gates that run at the same time on one host.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ci/gate_slots.py` (new), `src/devops_cli/commands/ci.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/options.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- `pyproject.toml` and `uv.lock` (`filelock` as a direct dependency), `config.example.yaml`.
- Tests: `tests/test_ci_gate_slots.py` and the `devops ci` command tests.
- Documents: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/CLI_REFERENCE.md` and `docs/TELEMETRY.md`. ADR 0014 stays as it is: it records the evidence of its date.

## Feasibility

- Library source: `filelock` 4.2.4 calls `fcntl.flock(fd, LOCK_EX | LOCK_NB)` in `filelock/_unix.py`. The operating system frees such a lock when the holder ends.
- Command output: a scratch probe held a slot in a child process, saw a second acquire refused, killed the child with SIGKILL, and took the slot 1 ms later. A killed agent cannot leak a slot.
- Command output: `uv tree --invert --package filelock` shows `filelock` 4.2.4 under `tldextract`, a direct dependency of devops-cli. The change adds no package.
- Data: the per-check durations come from the 399 passing entries of the CI cache of the host (`.data/cache/ci_cache-*.json`). Only `test`, `security` and `typecheck` have a p90 above 200 s.
- The divisor 8 of the default is a starting value, not a measurement. The first group of tasks measures one gate alone and two gates side by side, and `design.md` records the result.

## Existing Tool Considered

- `filelock` (tox-dev, maintained) covers the lock. It has no counting semaphore, so a loop over N lock files gives the count (about 15 lines). The change uses it and does not call `fcntl.flock` itself.
- GNU parallel `sem` is a counting semaphore, but it is a host package. The devcontainer and the runners must not need a host install.
- `systemd-run` with CPU quotas needs systemd, which the devcontainer does not run.
- POSIX named semaphores (`posix_ipc`) keep their count when a holder dies, which leaks slots.
- A merge queue does not apply. ADR 0014 records that a user account owns the repository.
- The change deletes no internal code. `security/mypy.py` has a `fcntl.flock` of its own for the mypy cache. It guards a different resource, so it stays.
