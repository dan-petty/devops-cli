# Task: The Stop-Signal Fake Records Signals Before Its Pids Are Visible (#1913)

**Issue**: [#1913](https://github.com/dan-petty/devops-cli/issues/1913)
**Scope**: scope/ci
**Feasibility**: I read `hung_script` in `tests/support/hung_children.py` and `_terminate_process_group_async` in `src/devops_cli/core/process.py` at `release/v0.2.39`. I ran `dash` to check how the fake child behaves. I reproduced the failure with a widened gap in the fake child. I measured the natural failure rate under a stress pinned to one core. The production code has no defect, so the change touches no file in `src/`. The section "Evidence" gives the details.

## Description

`hung_script` in `tests/support/hung_children.py` used to write the pid file (`echo "$$ $c" > "$0"`) and only then run `after_start`. For `records_stop_signals`, `after_start` set the traps that record `int` and `term`. Until then, the child ran under `trap "" INT TERM`, which ignores both signals. The tests send their first signal as soon as `watch.started` is true. The child lost a signal that came between the write of the pids and the traps. The test then failed with `(True, False, True, False)`, because `interrupted` was false.

- **The new part.** `hung_script` now has a part `after_spawn`. It runs after the grandchild starts and before the child writes the pids. `records_stop_signals` sets its traps there. `after_start` keeps its place after the pids. It holds nothing that a test needs from the child when it reads the pids. The docstrings say so.
- **The order of the traps.** The traps cannot go before the start of the grandchild. A grandchild that starts after the child sets a trap does not ignore SIGTERM. The test would then not check the SIGKILL.
- **The other users.** Besides the new test, only `tests/test_ci.py` and `tests/test_process.py` import `tests/support/hung_children.py`. Four tests use `records_stop_signals`. They are the three parameters of `test_a_second_signal_to_devops_ci_test_cannot_skip_the_sigkill` and `test_a_further_cancellation_during_the_stop_cannot_skip_its_sigkill`. The change fixes all four.
- **The users with no gap.** `interrupted_like_pytest` and the timeout test set their traps with `before` or `on_interrupt`. Both run before the child writes the pids. The one other `after_start` waits for a file and sends no signal.
- **The new test.** `tests/test_support_hung_children.py` makes the pid file a named pipe. The child waits at the write of its pids until the test opens the pipe. The test first waits until the child catches SIGINT and SIGTERM. It reads the mask of caught signals from the `SigCgt` line of `/proc/<pid>/status`. The child can be in this state only if it set the traps before it writes its pids. The test needs no sleep and has no race.
- **The bound on the pipe.** The test opens the pipe without a block and waits for the pids with `select`. A child that fails for another reason then fails the test with a clear message. A blocking read waited for a writer that never came, and the test ran until the timeout of the run.

## Evidence

- **Production code is ready.** The driver of `devops ci test` installs its SIGTERM and SIGHUP handlers before it starts the child (`_cancelled_by_stop_signals` in `src/devops_cli/commands/ci.py`). So the production code is ready when the test reads the pids.
- **Two facts of `dash`.** A grandchild that starts after `trap` sets a handler does not ignore SIGTERM. So the traps of the fake must follow the start of the grandchild. A trapped signal that interrupts a redirect makes `dash` stop it with "cannot create ...: Interrupted system call". So a test cannot send a signal while the child waits at the write of its pids. The new test reads `/proc/<pid>/status` and sends no signal.
- **The stress.** Every stress runs six busy Python loops (`nice -n 5`) and one pytest process, all under `taskset -c 3`. Each stress lasted at most 60 s. The busy loops end by themselves after 55 s. A scratch plugin (about 50 lines, in `.data/agent/scratch/`, not committed) repeats one test in one process. It skips the repeats that start after a deadline.
- **The natural rate before the fix.** The rate was too low to measure. `test_a_second_signal_to_devops_ci_test_cannot_skip_the_sigkill` passed 62 of 62 repeats, with the pytest process at nice 0, 5 and 10. `test_a_further_cancellation_during_the_stop_cannot_skip_its_sigkill` passed 400 of 400 repeats. The gap is the time between two commands of `sh`. The stress did not stop `sh` inside it.
- **A widened gap.** A scratch plugin put `sleep 0.5` first in `after_start`. This models a scheduler that holds `sh` back right after it writes its pids. Before the fix, the four tests failed in 4 of 4 repeats with `(True, False, True, False)`, the failure of the issue. After the fix, the same plugin leaves the four tests passing in 4 of 4 repeats.
- **The new test.** Before the fix, the new test failed after 30 s with `(False, True)`. The child did not catch the signals while it waited to write its pids. After the fix, it passes in under 1 s, and it passed 60 of 60 repeats under the stress. A scratch plugin made the child exit at once. The test then failed with `(False, False)` after 90 s, and it did not block.
- **After the fix.** `test_a_second_signal_to_devops_ci_test_cannot_skip_the_sigkill[SIGTERM]` passed 40 of 40 repeats under the stress. `test_a_further_cancellation_during_the_stop_cannot_skip_its_sigkill` passed 100 of 100.
- **The SIGKILL stays tested.** I changed `_terminate_process_group_async` so that it does not send the SIGKILL, and I ran the four tests. All four failed with `(True, True, False, False)`. The child and its grandchild ignore SIGINT and SIGTERM, so the stop code did not end them. I restored the file with `git checkout -- src/devops_cli/core/process.py`.

## Existing tools considered

- **The fix.** It needs no tool. It moves two `trap` commands in a shell script.
- **The mask of caught signals.** The new test reads it from `/proc/<pid>/status`, as `tests/support/hung_children.py` already reads `/proc/<pid>/stat`. `psutil` is not a dependency of the project. Its `Process` class (version 7.2.2) has no call for the mask of caught signals. The helper `_catches` has 4 lines. I estimate that it cost about 20,000 tokens and 30 minutes to write and check. It needs no upkeep, because the kernel interface is stable.
- **The read of the pipe.** The helper `_pids_the_child_writes_to` uses `os` and `select` from the standard library. I estimate that it cost about 10,000 tokens and 15 minutes.
- **The repeats.** `devops ci test --repeat` repeats whole test files, and `pytest-repeat` is not a dependency. So the scratch plugin repeats the one test.

## Acceptance Criteria

- [x] The fake child catches SIGINT and SIGTERM before it writes its pids. So it always records a signal that a test sends after it reads the pids.
- [x] The new test fails on the old order of `records_stop_signals` and passes on the new order.
- [x] The new test fails with a message, and does not block, when the child exits before it opens the pipe.
- [x] The four tests that use `records_stop_signals` fail when the stop code does not send the SIGKILL.
- [x] With the gap widened, the four tests failed 4 of 4 before the fix and passed 4 of 4 after it.
- [x] The stop-signal test of `tests/test_ci.py` passed 40 of 40 repeats under a stress pinned to one core.
- [x] No sleep and no longer deadline is part of the fix.
- [x] `uv run devops ci test tests/test_support_hung_children.py tests/test_process.py tests/test_ci.py` passes.
- Fail-to-pass: not applicable. The production code is correct and untouched, and the base passes on a quiet host.

## Deliverables

- [x] `tests/support/hung_children.py`: the part `after_spawn` of `hung_script`, `records_stop_signals` on it, and the docstrings.
- [x] `tests/test_support_hung_children.py`: the test that the fake catches the signals before its pids are visible.
- [x] `docs/agent/tasks/task-1913-stop-signal-tests-wait-until-the-fake-records-signals.md`.
- [x] `changelog.d/1913.md`.
