## Why

Three paths read a config file without the settings load, and each shows text of a file that PyYAML or ruamel.yaml cannot load (#2451). #1468 fixed the settings load only. A config file can hold a credential.

- `write_history._mapping` runs `yaml.safe_load` for the audit record of a write. ruamel.yaml accepts a local tag such as `!vault` and PyYAML does not. So `devops config unset ai.provider` failed with a `ConstructorError` that quotes the line with the value. The message went into the log line, the plain traceback and the Rich traceback.
- `round_trip.find` and `round_trip.edit` catch only `ruamel.yaml.YAMLError`. ruamel.yaml raises `ValueError` for `!!int <text>` and `KeyError` for `!!bool <text>`, and the message quotes the value.
- `write_history.redact_credentials` caught only `UnicodeDecodeError` and `yaml.YAMLError`, so `!!int <text>` and `!!bool <text>` escaped it in the same way.

`devops config audit-keys` already catches these errors since #1468. It reports the file as unaudited.

## What Changes

- New module `config/yaml_errors.py` with `load_yaml`. It runs a parse, and turns each load error into one ConfigurationError that names the file, the type of the error, and its line and column when the error has a mark. The error quotes no text. It has no cause and no context. The list of load errors and the reader of the mark move here from `config/settings.py`.
- `_read_config_file`, `write_history`, `round_trip.find` and `round_trip.edit` call `load_yaml`. `round_trip` passes the `YAMLError` of ruamel.yaml, so the helper does not import ruamel.yaml, which would add start time to every command.
- `commands/config.py` imports the load errors from the new module. It changes nothing else.
- The messages of the round trip and of the audit record now have the form `<action>: <file> is not valid YAML (<type>)<position>.`, with the line and the column when the error has them.

A message of a command changes, so the change carries a spec delta. It fits one pull request.

## Feasibility

Confirmed on 2026-11-04 on `origin/main` c9a61825 with PyYAML 6.0.3, with a script that calls each path with a fake value:

- `write_history._mapping(b"ai:\n  api_key: !vault FAKE-value-tag\n")` raised `ConstructorError`, and its message quotes the line.
- `_mapping` with `!!bool` raised `KeyError`. `round_trip.find` and `round_trip.edit` with `!!int` and `!!bool` raised `ValueError` and `KeyError`. With `!vault`, ruamel.yaml loads the file.
- `devops config unset ai.provider` on a file with `!vault` exited 1, and its output held the value. The command stops before it writes: `credential_paths` raises first. So the file and its audit record stay as they were.
- `devops config audit-keys` already handles `!!bool`: its `LookupError` covers `KeyError`.
- `import ruamel.yaml` takes 224 ms of cumulative import time, and the settings module does not import it now.

## Existing Tool Considered

PyYAML and ruamel.yaml give no option to leave the file text out of an error. The `yaml.MarkedYAMLError` mark holds the whole buffer. So the change wraps the parse in a function of about 40 lines, which is the pattern of `_read_config_file` from #1468, now shared. The cost is about 25,000 tokens and 1 hour, and about 2,000 tokens a year to keep. A second helper for each parser would copy the same logic, so there is one.

The change deletes `_YAML_LOAD_ERRORS` and `_yaml_error_location` from `config/settings.py`, and the three hand-written `except` blocks of `round_trip` and `write_history`.
