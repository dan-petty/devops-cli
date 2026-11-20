# Tasks

## 1. Test order

- [x] 1.1 Reproduce the random failure of the old order: run the handover test many times on a loaded host and count the runs in which `release()` returns `False`
  - Verification: a stress run outside the repository, 8 pytest processes on 4 CPUs with coverage; the old order failed in 4 of 200 runs, the new order in 0 of 200
- [x] 1.2 Call `lease_clock.leave()` after `await old.release()` returns, and state in the docstring of `leave()` when to call it
  - Verification: `$ uv run devops ci test tests/k8s/test_lease.py`

## 2. Documents

- [x] 2.1 Check that no document names the old order of the handover test
  - Verification: `$ uv run devops ci docs`
