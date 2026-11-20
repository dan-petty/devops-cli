# Tasks

## 1. Fake clock

- [x] 1.1 Reproduce the random failure: run the create-race test many times in 16 xdist workers on a loaded host and count the runs that count 3 creates
  - Verification: a stress run with a repeat plugin outside the repository; the old test failed in 6, 5 and 3 of 3,000 runs
- [x] 1.2 Write a test that fails on each run: a task that waits for a mark reads before a sleeper that is alone goes on
  - Verification: `$ uv run devops ci test tests/k8s/test_lease.py`
- [x] 1.3 Make `_LeaseClock.sleep` give control back to the event loop after each wake, as `asyncio.sleep` does
  - Verification: `$ uv run devops ci test tests/k8s/test_lease.py`

## 2. Documents

- [x] 2.1 Check that no document names the old behavior of the fake clock
  - Verification: `$ uv run devops ci docs`
