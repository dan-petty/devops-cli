# Proposal: #4525

## Why
A direct `uv run pytest` takes no gate slot (#4525). `addopts` give it `-n logical`, so on the shared 16-CPU host it starts 16 xdist workers beside a `devops ci` gate that holds the only slot. On 2026-11-11 such a run took 458% CPU beside the gate. The load average went from 2 to 41, the test row of the gate hit its 1800 s timeout, and mypy and bandit ran 6 to 9 times slower than on the GitHub runner. The slot limits only the runs of `devops ci`.

## What Changes
1. `gate_slot` sets `DEVOPS_CLI_GATE_SLOT_HELD=1` in the environment of its process while it holds a slot, and removes it after. The children of the holder, such as the pytest of the `devops ci` test row, get it. `build_subprocess_env` passes it through its `DEVOPS_CLI_` prefix.
2. The new `direct_run_slot` in `src/devops_cli/ci/gate_slots.py` holds a slot for a pytest run that no holder started. It waits as a gate waits, names the holders, and gives at most the CPUs of the process over the number of slots, and at least one. A run that finds `DEVOPS_CLI_GATE_SLOT_HELD` takes no slot and keeps its worker count.
3. The root `tests/conftest.py` wraps the xdist hook `pytest_xdist_auto_num_workers`. xdist calls this hook only for `-n logical` or `-n auto`, in the controller. The wrapper takes the count of xdist, which already reads `PYTEST_XDIST_AUTO_NUM_WORKERS`, and returns it capped by `direct_run_slot`. A run with `--collect-only`, `--help` or `--version` starts no worker and takes no slot. A run with an explicit `-n` count never calls the hook, so it takes no slot, as `devops ci test -n` takes none.
4. `CONTRIBUTING.md` and `docs/TESTING.md` say which pytest runs take a slot.

A direct pytest run now waits for a slot, which a person can see, so the change carries a spec delta.

## Capabilities
- `ci-gate-admission`: ADDED "A direct pytest run with automatic workers takes a slot" and "A run that a slot holder started takes no second slot".

## Impact
- A direct `uv run pytest` or `devops test run` with the default `-n logical` waits while every slot is held. On the 16-CPU host it then starts 16 workers, as before. `devops ci test <paths>` and a run with an explicit `-n` do not wait.
- The `devops ci` test row, its shards on the GitHub runner and the in-image suite hold the slot in the parent `devops` process. Their pytest sees the variable and keeps `-n logical`.
- A runner pod that sets `PYTEST_XDIST_AUTO_NUM_WORKERS` keeps that bound, capped by the CPUs of one slot.
- The change fits one pull request.

## Feasibility
- pytest-xdist 3.8.0 (`.venv`, `pytest_xdist-3.8.0.dist-info`) resolves `-n logical` and `-n auto` in its `tryfirst` `pytest_cmdline_main` (`xdist/plugin.py:305-316`), which calls the `firstresult` hook `pytest_xdist_auto_num_workers` (`xdist/newhooks.py:100`). Its default reads `PYTEST_XDIST_AUTO_NUM_WORKERS`, then the CPU count (`xdist/plugin.py:16-32`). pytest 9.1.1 calls `pytest_configure` later, in `wrap_session`. So the CI audit plan's `pytest_configure` is too late to set the count; the hook is the site.
- An xdist worker sets `numprocesses = None` before it calls `pytest_cmdline_main` (`xdist/remote.py:398`, `427`), so it never calls the hook.
- `tests/support/bootstrap.py` isolates HOME in a `trylast` `pytest_configure`. The hook runs before that, in the controller, which runs no test. It reads the settings and the data directory of the person, which `devops ci` also reads.
- Run with `DEVOPS_CLI_CI_GATE_SLOTS=4` while another process held all 4 slots on 16 CPUs, `uv run pytest tests/ci/test_ci_gate_slots.py -k number_of_slots` printed the wait line and waited. After the holders ended it started 4 workers. With the slots still held, the same run with `DEVOPS_CLI_GATE_SLOT_HELD=1` and `PYTEST_XDIST_AUTO_NUM_WORKERS=2`, the run with `-n 2`, and the run with `--collect-only` did not wait; the first two started 2 workers. The pull request comment has the commands and their output.

## Existing Tool Considered
pytest-xdist covers the worker count through its documented hook `pytest_xdist_auto_num_workers` and the variable `PYTEST_XDIST_AUTO_NUM_WORKERS`. `filelock` covers the slot, through the existing `gate_slot`. The change adds no dependency and no second lock: one hook wrapper of about 10 lines and one function of about 15 lines over `gate_slot`.
