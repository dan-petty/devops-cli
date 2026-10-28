# Proposal

## Why

Issue #1468: `_read_config_layers` in `src/devops_cli/config/settings.py` loads the global config file and the project config file with `yaml.safe_load`, and lets a `yaml.YAMLError` go up. The message of the PyYAML error quotes the line where the parser stopped. Thus each command that loads the settings prints that line on stderr, in the error text and in each traceback. A malformed line is where a pasted credential usually is. #1022 fixed this for `devops config audit-keys` only.

## What Changes

- `_read_config_layers` reads each config file through one helper. When the file is not valid YAML, the helper raises `ConfigurationError` with the message `Cannot load the settings: <file> is not valid YAML (<error type>) at line <n>, column <n>.` The line and the column come from the `problem_mark` of the PyYAML error. The message quotes no text of the file.
- The helper gives the same message for the other errors of the read and the parse, and catches each by name. The safe loader of PyYAML raises `ValueError`, `KeyError`, `IndexError` or `AttributeError` for a tagged value that it cannot build, such as `!!int <text>`, and the message of that error can quote the value. It raises `RecursionError` for a document that nests too deep. A file that is not UTF-8 raises `UnicodeDecodeError`. These errors have no mark, so the message has no line and no column. An `OSError` goes up as it did before.
- The helper raises the error after its `except` block. Thus the error has no `__cause__` and no `__context__`, and no traceback or log record holds the PyYAML error. The `Mark` of a PyYAML error holds the full text of the file in its `buffer`, so `raise ... from None` is not sufficient: it only hides `__context__` from the traceback.
- `devops config get` reports a `ConfigurationError` from the load of the settings on one line and exits 1, with no traceback. It uses `exit_on_error`, as `devops config unset` does.
- `main._delegate` raises the exit of a command that returned a non-zero exit code in the `else` clause of its `try`. Before, it raised that exit inside the `try`, and its own `except Exception` caught it. That clause counted the command a second time in `devops_cli_command_total`, set `cli.exit_code` to 1, and logged `Command '<name>' failed: <code>` with a traceback. When the settings do not load, telemetry is off and no handler is on the root logger, so Python printed that record and its traceback on stderr after the one-line error.
- The message and the exit code are observable, so the change carries a spec delta for the `config-commands` capability. The count, the `cli.exit_code` and the log record of a command that reports its own failure are observable in telemetry, so the change also carries a delta for the `command-telemetry` capability.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: a config file that is not valid YAML stops the load of the settings with an error that names the file, the line and the column, and that quotes no text of the file.
- `command-telemetry`: a command that reports its own failure and exits with a non-zero code is counted one time, its span records that code, and `_delegate` logs no record for the exit.

## Impact

- `src/devops_cli/config/settings.py`: `_read_config_layers` reads each layer through `_read_config_file`, which raises the error.
- `src/devops_cli/lang/en/errors.py`: the message `ConfigErrorMessages.not_yaml`.
- `src/devops_cli/commands/config.py`: `devops config get` reports the error with `exit_on_error(ConfigurationError)`.
- `src/devops_cli/main.py`: `_delegate` raises the non-zero exit of a command outside its `except` clauses.
- `src/devops_cli/docs/generator.py` and the generated `docs/TELEMETRY.md`: the count, the exit code and the log of a command that reports its own failure.
- `tests/config/test_config_file_that_is_not_yaml.py`, `tests/commands/test_config.py`, `tests/test_config_env_overrides.py` and `tests/test_otel_command_coverage.py`.
- The knowledge base pages `src/devops_cli/ai/knowledge_base/devops_cli/configuration_and_settings.md` and `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pyyaml_jinja2.md`. The YAML example of the second page quoted the text of the PyYAML error in the error that it raised.

## Feasibility

- Reproduced on `origin/main` (19412fa9) with PyYAML 6.0.3. A temporary file holds `ai:` and `  api_key: FAKE-value: x`, and `DEVOPS_CLI_CONFIG` names it. `devops config get ai.provider` exits 1. Its stderr holds the line `api_key: FAKE-value: x` three times: in the log line `Command 'config' failed: mapping values are not allowed here ...`, in the plain traceback, and in the Rich traceback.
- In PyYAML 6.0.3, `yaml.safe_load` of that text raises `ScannerError`, a `MarkedYAMLError`. Its `problem_mark` has the 0-based `line` 1 and `column` 21, and its `buffer` attribute holds the full text of the document, with the `FAKE-` value.
- In PyYAML 6.0.3, `yaml.safe_load` of `a: !!int FAKE-value` raises `ValueError: invalid literal for int() with base 10: 'FAKE-value'`, of `a: !!bool FAKE-value` raises `KeyError: 'fake-value'`, and of `a: !!timestamp FAKE-value` raises `AttributeError`. None of them is a `yaml.YAMLError`. `Path.read_text` of a file with the byte `0xE9` raises `UnicodeDecodeError`, and its `object` attribute holds the bytes of the file.
- `src/devops_cli/commands/config.py::_scan_yaml_for_secret_keys` (#1022) and `src/devops_cli/config/round_trip.py` already report a YAML error by its type name and position, with no text of the file.
- `exit_on_error` in `src/devops_cli/core/cli.py` prints the message of a `DevOpsCLIError` with no traceback and exits with its `exit_code`. `devops config unset` already uses it for `ConfigurationError`.
- With `exit_on_error` alone, `devops config get ai.provider` against that file printed the one-line error, then `Command 'config' failed: 1` and the traceback of `typer.exceptions.Exit: 1`. `typer.Exit` is a `RuntimeError`, not a `typer.TyperException`, so the `except Exception` clause of `_delegate` caught the exit that the `try` raised.
- The same clause catches the exit of each delegated command that returns a non-zero exit code. With a config file that loads, `devops config unset ai.no_such_key` on `origin/main` exits 1 and logs the record `Command 'config' failed: 1` with `exc_info`. The logging bridge of telemetry takes that record, so stderr shows only the one-line error. When the settings do not load, the bridge is not attached, and Python's last-resort handler prints the record and its traceback on stderr.

## Existing Tool Considered

- PyYAML, which loads the settings, gives the position of the error in `MarkedYAMLError.problem_mark`. The change uses that position and the type name of the error. It adds no dependency.
- `exit_on_error`, the exit seam that `devops config unset` already uses, reports the error. #1006 makes one exit seam for every command, and this change adds no second one.
- The change deletes the path that let a `yaml.YAMLError` leave `load_settings`.
