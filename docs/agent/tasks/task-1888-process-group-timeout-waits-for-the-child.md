# Task: The Process-Group Timeout Test Starts Its Timeout After the Child Exists (#1888)

**Issue**: [#1888](https://github.com/dan-petty/devops-cli/issues/1888)
**Scope**: scope/core
**Feasibility**: I read `run_subprocess_async` in `src/devops_cli/core/process.py` at `release/v0.2.39` (b2b67df5). The run waits with `asyncio.wait_for(proc.communicate(), timeout)`, so its timeout counts from the moment the run starts waiting for its child. I reproduced the failure under a stress pinned to one core with `taskset -c 3`, described below. The old text of the test failed in 15 of 15 runs at `assert pid_file.exists()`. The rewritten test passed 40 of 40 runs under the same stress. In a probe, `time-machine` moved `time.time()` but not `loop.time()` or `time.monotonic()`.

## Description

`test_run_subprocess_async_timeout_kills_process_group` in `tests/test_process.py` started a Python child with a timeout of 0.6 s. The child had to start, start a second Python process and write a pid file before the timeout fired. On a busy host the timeout fired first. The pid file did not exist, and `assert pid_file.exists()` failed.

The test now makes the timeout count from after the child exists. A spawn wrapper replaces `asyncio.create_subprocess_exec`, as `test_a_cancellation_after_the_child_exited_stays_a_cancellation` does in the same file. The wrapper returns only once the child has written its pids. The run starts to wait for its child after the spawn returns. So a timeout of 0.2 s (`STARTED_RUN_TIMEOUT_SECONDS`) fires after the child and its grandchild exist. The child hangs, so the timeout always fires.

The child and the grandchild now come from `hung_with_grandchild`, and `watching` reads through pidfds whether both exited. This replaces the hand-written Python script, the read of the pid file and `os.kill(pid, 0)`. The only wait with a bound is `_until`, which uses `THREAD_HANDOFF_BOUND_SECONDS`. The production code has no defect, and the change touches no file in `src/`.

**The test still proves the group stop.** I changed `_terminate_process_group_async` to kill only the leader. The rewritten test then failed after 30.2 s of waiting for the grandchild to exit. I restored the file with `git checkout -- src/devops_cli/core/process.py`.

**The stress.** The stress is six busy Python loops (`nice -n 5`) and one pytest process, all started under `taskset -c 3`. The pytest process lowers its own priority to nice 15 after it collects the tests. Each window lasted at most 60 s, and the busy loops end by themselves after 55 s. A scratch plugin (about 20 lines, in `.data/agent/scratch/`, not committed) repeats one test in one process.

**The measurements.** The old text of the test, copied unchanged to scratch space, failed in 15 of 15 runs. The old test in `tests/test_process.py` failed in 19 of the first 19 runs of one window. The 11 runs after them passed, and they fell after the 55 s of the busy loops. The rewritten test passed 10 of 10 runs, then 15 of 15, then 15 of 15, and each call took about 1 s. On a quiet host the call takes 0.22 s. With the pytest process at nice 0 (30 runs), nice 5 (30 runs) or nice 10 (15 runs), the old text passed every run, so the stress needs the lower priority.

**The design options.** The first option was a long timeout, with the test moving the event loop's clock past it once the pids exist. I built it and rejected it. The child can exist before the run reaches `wait_for`, so the jump can come before the timer exists. A probe showed the timeout firing 30 s after the jump. A second option, a timeout that grows with each attempt, adds retries inside a test, and each failed attempt kills the group before its grandchild exists. I did not build it. A third option is a virtual-clock library for asyncio (for example `aiotools`). It is a new dependency, which this task does not allow. The spawn wrapper needs no clock and no dependency.

**The tools considered.** `devops ci test --repeat` repeats whole test files, and the stress needed one test repeated. `pytest-repeat` is not a dependency. The shared helpers `tests/support/hung_children.py` and `tests/support/waits.py` cover the child, the grandchild and the waits, so the change builds no helper.

The fail-to-pass check does not apply. The production code is correct, and the old and the new text both pass on a quiet host, so a replay on the base passes. The stress runs above show the difference.

## Acceptance Criteria

- [x] The timeout of the test fires after the child and its grandchild exist, whatever the load: the spawn returns only once the child has written its pids.
- [x] The timeout path of `run_subprocess_async` still fires and still stops the whole group: the test fails when the stop kills only the leader.
- [x] The old text failed in 15 of 15 runs under the stress, and the new test passed 40 of 40 runs under the same stress.
- [x] The test takes 0.22 s on a quiet host.
- [x] `uv run devops ci test tests/test_process.py` passes.
- Fail-to-pass: not applicable. The production code is correct and the base passes on a quiet host.

## Deliverables

- [x] `tests/test_process.py`: the spawn wrapper, `STARTED_RUN_TIMEOUT_SECONDS`, and the test on `hung_with_grandchild` and `watching`.
- [x] `docs/agent/tasks/task-1888-process-group-timeout-waits-for-the-child.md`.
- [x] `changelog.d/1888.md`.
- Not done: `tests/test_process.py:433` (`test_a_run_that_hangs_after_its_summary_line_is_stopped_at_its_bound_with_its_group`) and `tests/test_process.py:459` (`test_a_timed_out_check_is_stopped_with_sigterm_first_and_reports_as_before`) give a real `sh` child a timeout of `HUNG_RUN_TIMEOUT_SECONDS` (1.0 s) that counts from the spawn, and they wait for its pids inside it. They can race the same way, and the spawn wrapper of this test can serve them. Under the same stress they passed 4 of 4, because `sh` starts faster than two Python processes. A person files the follow-up issue.
- Not done: `tests/test_process.py:117`, `tests/test_host_sandbox.py:516` and `tests/test_devcontainer.py:1926` use a short timeout that the test expects to fire, so they do not race, as the issue says. No follow-up is needed.
