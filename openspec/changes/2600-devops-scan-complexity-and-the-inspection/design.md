# Design

## Decisions

- **Keep the McCabe port in `src/devops_cli/core/code_metrics.py` as the one source of complexity for the two readers.** Ruff is a development dependency, not a runtime dependency. Its JSON output has no field for the figure; the figure is only in the `message` string. The port is one module of the standard library, and `tests/core/test_code_metrics.py` holds 12 figures that were taken from `ruff check --select C901` with `max-complexity=0`. The test does not run Ruff, so a later change of Ruff counting does not fail it.
- **State the reason in the module docstring.** The docstring is the place a reader of the code sees first. This design and the archive keep the longer record.

## Rejected alternatives

- **Read the figure from a Ruff subprocess per scan.** The command is `ruff check --select C901 --config 'lint.mccabe.max-complexity=0' --output-format json`. Ruff is not a runtime dependency (`pyproject.toml`, `[dependency-groups] dev`). The figure is in the `message` string, so the code must parse text. Each scan needs one more process.
- **Add Ruff as a runtime dependency.** It adds a native binary to every install of `devops`. The port is 89 lines of code that need no install.
