# Design

## Context

`load_settings` calls `_merged_config_data`, which calls `_read_config_layers`. That function runs `yaml.safe_load` on the global config file and on the project config file. A PyYAML error goes up through every command that loads the settings. `src/devops_cli/main.py::_delegate` logs it with `exc_info=True`, and the root Typer app prints its Rich traceback. Each of the three outputs quotes the line where the parser stopped.

## Goals / Non-Goals

**Goals:**
- No output, log record or exception chain of a settings load holds text of a config file that is not valid YAML.
- The error names the file, the line and the column, so a person can find the line.
- `devops config get` prints the error on one line and exits 1, with no traceback.

**Non-Goals:**
- One exit seam for every command group. #1006 owns that change. Until then, a command other than `devops config get` and `devops config unset` prints a traceback for a `ConfigurationError`, but that traceback holds no text of the file.
- A change to `devops config audit-keys`, which already reports a `yaml.YAMLError` with no text (#1022).
- The config paths that do not load the settings: the audit record of a config write (`write_history._mapping`), the round-trip of `config set` and `config unset` (`round_trip`), and the `KeyError` of `!!bool <text>` in `devops config audit-keys`. They can still show text of a file that PyYAML or ruamel.yaml cannot load. #2451 owns them.
- The validation errors of pydantic for a value of the wrong type. They are a different error path.

## Decisions

### 1. One helper reads each config layer
- Decision: `_read_config_file(path)` reads and parses one config file. `_read_config_layers` calls it for the global file and for the project file.
- Rationale: The two layers had two copies of the same `yaml.safe_load` call. One helper gives one place for the error.
- A second helper, `_yaml_error_location`, reads the position from the `problem_mark`. Thus the frame that raises the error holds no `Mark` in its local variables.

### 2. The message holds the type name of the error and its position, not the problem text
- Decision: The message is `Cannot load the settings: <file> is not valid YAML (<error type>) at line <n>, column <n>.` The line and the column are 1-based, as PyYAML prints them. An error with no `problem_mark` gives the message with no position.
- Rationale: The problem text of some PyYAML errors quotes text of the file, such as `found undefined alias 'name'` or `found character '\t' that cannot start any token`. The type name and the position are always safe. `_scan_yaml_for_secret_keys` (#1022) and `round_trip` already use the type name.
- Alternative considered: Add `exc.problem`, such as `mapping values are not allowed here`.
  - Rejected: The problem text is a format string with file text in it for some errors. A filter of safe problem strings is a list to keep current with PyYAML.

### 3. The error is raised after the `except` block
- Decision: The `except` block keeps only the type name and the position. The helper raises `ConfigurationError` after the block, so the new error has no `__cause__` and no `__context__`.
- Rationale: `raise ... from None` sets `__suppress_context__`, but `__context__` still holds the PyYAML error. Its `problem_mark.buffer` holds the full text of the file. A tool that walks `__context__` would get the credential.
- Alternative considered: `raise ConfigurationError(...) from None`, as the issue proposes.
  - Rejected: PyYAML 6.0.3 keeps the full text of the document in `Mark.buffer`, and `from None` keeps the error in `__context__`.

### 4. The helper catches the errors of the read and the parse by name
- Decision: The `except` block catches `(yaml.YAMLError, ValueError, LookupError, AttributeError, RecursionError)`. Each error that it catches gives the same message. An error with no mark gives the message with no position. An `OSError` goes up as it did before.
- Rationale: The safe loader of PyYAML raises `ValueError`, `KeyError`, `IndexError` or `AttributeError` for a tagged value that it cannot build, such as `!!int <text>`, `!!bool <text>` or `!!int ''`. These errors are not `yaml.YAMLError`, and the messages of some quote the value. The composer of PyYAML calls itself for each level of a nested document, so a document that nests too deep raises `RecursionError`. The decode of a file that is not UTF-8 raises `UnicodeDecodeError`, a `ValueError` whose `object` attribute holds the bytes of the file. The list comes from the constructors of `SafeConstructor` in PyYAML 6.0.3 and from a run of `yaml.safe_load` on each kind of bad value. `tests/config/test_config_file_that_is_not_yaml.py` holds a file for each type, so a type that leaves the list fails a test. An `OSError` names only the file and is not a YAML problem.
- Alternative considered: Catch `Exception`, after an `except OSError: raise` block.
  - Rejected: A blind `except Exception` is a swallowed failure (BLE001), and `tests/test_swallowed_failures_ratchet.py` refuses a new one in `src/`. The ceiling of `config/settings.py` does not go up.

### 5. `devops config get` uses the existing exit seam
- Decision: `devops config get` loads the settings inside `exit_on_error(ConfigurationError)`.
- Rationale: The issue asks that `devops config get ai.provider` exits 1 with the message and no traceback. `exit_on_error` is the seam that `devops config unset` already uses. The same seam also reports the error of an unknown key (#2201) on one line.
- Alternative considered: Build the `config` app with `new_typer(exit_on=ConfigurationError)`.
  - Rejected: That change also wraps each `config` command in a trace span and adds the `-h` option. It is part of #1006, which moves every command onto one seam.
- Alternative considered: Catch `DevOpsCLIError` in `main._delegate` for all commands.
  - Rejected: #1006 decides where the one exit seam is, and chose the wrapper of `OTelTyper.command`.

### 6. `_delegate` raises a non-zero exit outside its `except` clauses
- Decision: The `if exit_code != 0: raise typer.Exit(exit_code)` lines move from the body of the `try` in `main._delegate` to its `else` clause.
- Rationale: `typer.Exit` is a `RuntimeError`. Raised in the `try`, it went to `except Exception`, which logged `Command '<name>' failed: <code>` with `exc_info=True`. When the settings do not load, telemetry is off, the root logger has no handler, and Python's last-resort handler printed that record and its traceback on stderr. Thus `devops config get` showed a traceback after its one-line error. The same clause counted the command a second time in `devops_cli_command_total` and set `cli.exit_code` to 1 for each exit code. The `else` clause runs only when the `try` raised nothing, and the `finally` clause still flushes the tracer.
- Consequence: The command already printed its error, and the span and `devops_cli_command_total` record the failure with its real exit code. Thus `_delegate` logs no record for the exit. The error stream of the `devops-cli` dashboard keeps the records of unhandled exceptions, as the `command-telemetry` spec says. `tests/test_otel_command_coverage.py` holds the count, the exit code and the absence of a record, so the exit cannot go back into the `try` with no failed test.
- Alternative considered: Add `except typer.Exit: raise` before `except Exception`.
  - Rejected: The clause would also catch an exit that the command raises, which Click already turns into the return value. The `else` clause is the Python form for code that runs only after a `try` that raised nothing.

## Risks / Trade-offs

- [A caller caught `yaml.YAMLError`, `ValueError` or `UnicodeDecodeError` from `load_settings`] -> No caller in `src` does. `telemetry/tracer.py::_resolve_telemetry_settings` catches `Exception`, so it still falls back to the telemetry variables.
- [The error stream of the `devops-cli` dashboard no longer shows a command that reports its own failure] -> Before, it showed that command only through the record of the misplaced exit, `Command '<name>' failed: <code>`, with the traceback of `typer.Exit`. No panel or alert reads that text. The span status `error`, `cli.exit_code` and `devops_cli_command_total` with the status `error` record the failure.
- [An error with no mark, such as the `ValueError` of `!!int <text>`, gives no line and no column] -> The message names the file and the type of the error. A tagged value in a config file is rare.
- [The message has less detail than the PyYAML error] -> The file, the line, the column and the error type locate the problem. The person opens the file at that line.
