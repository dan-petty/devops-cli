# Design

## Decisions
- **The slot is taken in a wrapper of `pytest_xdist_auto_num_workers`.** xdist calls the hook only when `-n` is `logical` or `auto`, only in the controller, and before it sets `config.option.tx`. That is the exact set of runs that start one worker for each CPU. The wrapper takes the count of xdist and returns it capped, so the variable `PYTEST_XDIST_AUTO_NUM_WORKERS` and the choice between `logical` and `auto` stay with xdist.
- **The cap is the CPUs of the process over the number of slots, and at least one.** One slot on 16 CPUs gives 16, which `-n logical` gave before. Two slots on 32 CPUs give 16 each. A setting of 4 slots on 16 CPUs gives 4.
- **The holder marks its environment.** `gate_slot` sets `DEVOPS_CLI_GATE_SLOT_HELD=1` while it holds the slot. The pytest of the `devops ci` test row, and a pytest that a test starts inside a direct run, inherit it and take no second slot. Without the mark they would wait for the slot of their own parent until the check timeout.
- **The hook lives in the root `tests/conftest.py`.** It must be registered before `pytest_cmdline_main`. The support modules of `tests/support/` are registered later, in `pytest_configure`. `optionalhook=True` keeps a run with `-p no:xdist` valid.
- **The hook runs before HOME is isolated.** It needs the settings and the data directory of the person, the same ones `devops ci` reads, so that both share one set of slots. The controller of an xdist run runs no test.
- **The logic lives in `src/devops_cli/ci/gate_slots.py`.** A test file may not import a conftest, so `direct_run_slot` holds the behavior that tests check, and the conftest only calls it.

## Rejected alternatives
- **Take the slot in `pytest_configure` (the CI audit plan).** xdist sets the worker count in `pytest_cmdline_main`, before `pytest_configure` (`xdist/plugin.py:305-316`). A `pytest_configure` hook could only rewrite `config.option.tx`, an internal option of xdist.
- **Narrow a direct run to 4 workers while a slot is held (the first design of the issue).** The run still loads the host beside the gate, and it does not wait. The CI audit chose the wait.
- **Set `PYTEST_XDIST_AUTO_NUM_WORKERS` from the hook.** The default of xdist reads it, but a value that the person or a runner pod set would then need its own merge rule. The wrapper gets the result of that default and caps it.
- **Compare the holder process number with the pytest parent.** `devops ci` starts pytest through `uv run`, so the holder is the grandparent, and a test can start pytest deeper. The variable reaches every child.
- **Take a slot for every direct run, also with an explicit `-n`.** `devops ci test -n <count>` takes no slot, and a person who sets the count has chosen the load. A serial run of one file would wait up to the full gate time.
