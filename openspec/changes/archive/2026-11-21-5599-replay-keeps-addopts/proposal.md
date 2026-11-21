# Proposal: #5599

## Why

The replay of `devops ci fail-to-pass` starts pytest with `-o addopts=`, which sets the `addopts` of the tree to an empty value. `tests/commands/test_test_selection.py::test_the_full_gate_collects_every_test_module` reads `addopts` with `pytestconfig.getini`, so it fails in the replay on each base and on each head, but it passes in a normal run. A fix that changes `tests/commands/test_test_selection.py` gets a false failure on base, and when the head replay fails too, the check exits 1. The empty `addopts` also loads pytest-randomly and the logfire plugins, and removes the Hypothesis `ci` profile, so the replay is not a normal run. Closes #5599.

## What Changes

- The replay keeps the `addopts` of the tree, and gives `-n 0` in place of `-o addopts=`. pytest puts `addopts` before the command line, so `-n 0` overrides `-n logical`: the replay starts no xdist worker and takes no gate slot, as before.
- The other replay options do not change: `-p no:cacheprovider`, `--continue-on-collection-errors` and `--junitxml`.

## Capabilities

- `ci-fail-to-pass`: ADDED requirement 'The replay keeps the addopts of the tree'.

## Impact

A test that reads `addopts`, or that needs the plugins or the Hypothesis profile of `addopts`, passes in the replay as in a normal run. The base replay, the plain base replay and the head replay use the same options. No new option, failure class or setting.

## Feasibility

- pytest 9.2.0: `uv run python -m pytest -o addopts= -p no:cacheprovider tests/commands/test_test_selection.py::test_the_full_gate_collects_every_test_module` fails with `At index 1 diff: [] != ['-n', 'logical', ...]`, and the run prints `Using --randomly-seed=`. The same test with `-n 0` in place of `-o addopts=` passes.
- `uv run python -m pytest -n 0 -p no:cacheprovider --continue-on-collection-errors tests/commands/test_test_selection.py`: 105 passed.
- pytest-xdist 3.8.0 (`xdist/plugin.py`): distribution mode needs a `tx` value, and `-n 0` gives none. Only `-n auto` or `-n logical` calls `pytest_xdist_auto_num_workers`, which takes the gate slot of `tests/conftest.py`.
- `addopts` holds no `--cov`. Only the test step of `devops ci` gives `--cov=src`, so the replay needs no `--no-cov`.

## Existing Tool Considered

pytest and pytest-xdist cover the need: `-n 0` stops the workers and keeps `addopts`. The `[tool.mutmut]` table of `pyproject.toml` uses the same `-n 0` for the same reason. The change deletes the `-o addopts=` option of the replay and adds no code.
