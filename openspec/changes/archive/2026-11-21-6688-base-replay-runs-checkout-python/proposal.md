# Proposal: #6688

## Why
Since #6517 the runner image installs no dev group, and the bootstrap of the Job installs it into the venv of the checkout. The base replay of a behavior group still starts `sys.executable -m pytest`, and in the Job that is `/app/.venv/bin/python`, which has no pytest. So each behavior group stops at its first exit check with "No module named pytest", and the Job discards the work. Closes #6688.

## What Changes
- The base replay of an implement step runs the pytest of `<checkout>/.venv/bin/python`, by its absolute path, also when a person runs a step in the current folder.
- `replay_on_base` and `pytest_replay_argv` take the interpreter as a keyword argument. `devops ci fail-to-pass` keeps `sys.executable`, because its process runs in the venv of the checkout.

## Capabilities
- `roadmap-implement-runner`: adds the requirement that the base replay of a step runs the pytest of the checkout. The requirement on the PATH of the checks no longer counts the base replay.

## Impact
- `src/devops_cli/roadmap/implement/implement_base_replay.py`, `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/roadmap/runner_tools.py`.
- No setting, command or output changes.

## Feasibility
Four stop reports of 2026-11-21 (#6603, #4147, #6522, #6627) show `/app/.venv/bin/python: No module named pytest`. `_bootstrap` in `implement_run.py` runs before the first step of an item, so the venv of the checkout exists when a step replays its tests. The test of this change fails on main: the replay names the Python of the test process.

## Existing Tool Considered
None applies: the change passes an existing interpreter path to the project's own replay and adds no mechanism.
