# Design

## Context

See proposal.md for the motivation and the measured durations.

- `all_checks` in `src/devops_cli/commands/ci.py` runs every selected check at once with `asyncio.gather`. The `test` check starts pytest with `-n logical`, one worker for each CPU. Nothing coordinates two `devops ci` processes.
- All worktrees of devops-cli share one data directory: `resolve_data_path` resolves a relative path under the main worktree.
- `cleanup_data_directory` removes entries by age, only inside `reviews`, `analysis`, `logs`, `traces`, `benchmarks` and `cache`. A direct child of the data directory is never removed.
- The pre-push hook runs `devops ci --check --only lint,format,actionlint,zizmor`. The `Static Analysis` job of CI runs `devops ci --check --no-cache --skip test,outdated`, and the `Tests & Coverage` job runs `--only test`. The runner has 4 CPUs.
- `devops ci` has no settings section today. Its tunables are `DEFAULT_CI_*` constants.

## Goals / Non-Goals

**Goals:**

- Gates that start together take turns, so each gate runs with the CPU it needs.
- A crashed or killed agent cannot block the others.
- The pre-push hook and a run on a quiet host see no change.

**Non-Goals:**

- No limit on other heavy commands (`devops review`, `devops ci mutate`, `devops ai`). They have other resource profiles. A later issue can reuse the slots if the data shows a need.
- No first-in first-out order. A waiting run polls, so the order of two waiting runs is not fixed.
- No cap on the number of pytest workers of a gate. The limit is on how many gates run, not on the shape of one gate.
- No change to the worktree layout. Issue-claim and worktree-creation commands are separate items.

## Decisions

**One slot is one `devops ci` process, not one check.** A gate runs more than a dozen checks at once. A slot for each check would let one gate take every slot. Alternative rejected: a slot for each heavy check. Evidence: `all_checks` starts `test`, `security` and `typecheck` together, so a gate would hold three slots and a host with two slots could never start one.

**A slot is one lock file taken with `filelock.FileLock(timeout=0)`.** The gate tries `slot-0.lock` to `slot-<n-1>.lock` in turn. If none is free, it sleeps and tries again. The lock is `fcntl.flock`, so the operating system frees it when the process ends. Alternatives rejected:

- GNU parallel `sem`: a host package, and the devcontainer and the runners must not need one.
- `systemd-run` with CPU quotas: the devcontainer runs no systemd.
- `posix_ipc` named semaphores: the count survives a dead holder, so a killed agent leaks a slot. The probe of the proposal shows that an `flock` slot is free 1 ms after SIGKILL.
- A ticket queue for first-in first-out order: it needs shared state that a dead process must clean up. Two or three waiting agents do not need the order.

**The slot directory is `ci-gate-slots` directly under `data.dir`.** It is shared by every worktree through `resolve_data_path`. It is outside the six directories that `workspace clean` prunes, so the clean command cannot remove a lock file that a gate holds. Alternative rejected: the cache directory, which `workspace clean` prunes by age. A removed lock file would let a second gate create a new file and hold the same slot.

**The holder writes `<pid> <worktree root>` into its slot file after it takes the lock.** A waiting run reads the files of the slots that it cannot lock, so it can say who holds them. The text is only a hint: the lock is the truth. Only a locked slot is read, so the text of a free slot is never shown.

**The heavy checks are marked on `CheckSpec`, not named in the gate.** `get_check_specs` is the one table of checks, so the flag sits beside the command it describes. The gate asks `any(spec.heavy for spec in selected_specs)`. The threshold is a p90 above 200 s in the 399 passing entries of the CI cache: `test` (526 s), `security` (450 s) and `typecheck` (239 s). The next check, `openspec`, has a p90 of 88 s. Alternative rejected: a slot for every run. The pre-push hook would queue behind a gate of ten minutes, and ADR 0014 made that hook fast on purpose.

**The slot is taken in the command, after the cached verdict and before the clock starts.** In `all_checks` the call sits between `_try_fast_cached_ci` and `start_time`, so a cached run never waits and the queue time stays out of `total_elapsed`, the summary and `_warn_when_over_budget`. `coverage` takes it before `_run`. `test` takes it only when `workers` is `None`, the case in which pytest keeps the `-n logical` of `addopts`: a run narrowed by paths gets `-n 0` or `-n 4` from `_narrowed_workers`, and a person's own `-n` is a choice that the command respects. A dry run returns before the call. The slot is released in a `finally` block by a context manager, so an exception cannot leave it held.

**The number of slots is `ci.gate_slots`, else `max(1, process_cpu_count // 16)`.** A new `CIConfig` section holds one field, `gate_slots: int | None`, with a minimum of 1. The default adapts to the host: 16 CPUs give 1 slot, 32 give 2, and the 4-CPU runner gives 1, where a single job never waits. The divisor comes from the measurement below. Alternative rejected: a divisor of 8, which gives 2 slots on this host. Two gates side by side finished both jobs only 11% sooner than two gates in turn, took 1.77 times as long each, and ran past the 300 s budget of the `test` step.

**The wait is a poll through the clock seam.** The poll interval is 2 s. `gate_slot` waits with `devops_cli.core.clock.sleep` and reads the time with `devops_cli.core.clock.monotonic`, each looked up when it is called. The `clock` fixture of the tests replaces both, so a test waits no real time. The wait message prints once, when the first poll fails. The time waited is returned to the caller, which records it.

**The wait is a plain blocking loop in the main thread.** A stop signal reaches Python's default handlers there: SIGINT raises `KeyboardInterrupt` and SIGTERM ends the process. Both end the wait and release the lock, because the operating system frees `flock` at exit. The `ci-test-stop` handlers install only while pytest runs, so they do not apply here.

### Measurement

On 2026-10-27, on a 16-CPU host with a load average of 2 before the first run, `uv run devops ci test` ran the full suite (11189 tests, `-n logical`):

| Run | Time of pytest | Wall time | Peak process ids of the container |
| :--- | ---: | ---: | ---: |
| One gate alone | 247 s | 256 s | not read |
| Two gates side by side | 440 s and 442 s | 454 s | 926 of 2048 |

- Every test passed in every run. The exit status was 1 each time because the workspace tripwire saw files of the change edited during the run.
- Two gates in turn take 512 s for both jobs and finish the first at 256 s. Two gates side by side finish both at 454 s, which is 11% sooner, and finish the first 198 s later. The mean wait for a result is 384 s in turn and 454 s side by side.
- A gate alone is inside the 300 s budget of the `test` step, and a gate in a pair is not.
- A pair uses 926 process ids, and the container allows 2048. Five gates side by side would pass the limit.

## Risks / Trade-offs

- [A person runs `workspace clean` while a gate holds a slot] → The slot directory is outside the pruned directories, so the clean command does not touch it.
- [A holder hangs and keeps its slot] → Each check has a timeout of 1800 s (`DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`), so a gate is bounded. A person sees the holder in the wait message and can end the process. A wait has no timeout of its own, because a timeout would start a gate beside the others and bring back the load.
- [Two containers share one data directory on a network file system] → `flock` is not reliable there. The workspace sits on a local file system, and `devops ci` already warns about a slow mount (`gate_root_slow_mount`). Containers do not share CPUs, so a slot limit across them would be wrong anyway.
- [The default of 1 slot on 16 CPUs is too low for a host with spare memory and CPU] → `ci.gate_slots` and `DEVOPS_CLI_CI_GATE_SLOTS` set it. The metric `ci.gate_slot_wait_seconds` shows the wait, so a person can tune it from data.
- [An agent waits a long time and looks stuck] → The wait message names the process and the worktree that hold each slot, so a person or an agent can see what it waits for.
