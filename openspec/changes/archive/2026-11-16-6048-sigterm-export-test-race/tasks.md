# Tasks

## 1. Behavior

- [x] 1.1 Reproduce the hang: run the child of the test 24 at a time and count the children that live on after SIGTERM
  - Verification: a stress script outside the repository; the old child hung in 41 of 600 runs, in `__do_sys_pause`
- [x] 1.2 Make the child wait on its wakeup pipe, and make the test wait with `wait_while_running`, send SIGTERM after any line, and kill and reap the child in `finally`
  - Verification: `$ uv run devops ci test tests/telemetry/test_sigterm_export.py`; the same stress script hung in 0 of 1,200 runs

## 2. Documents

- [x] 2.1 Check that no document names the old wait of the child
  - Verification: `$ uv run devops ci docs`
