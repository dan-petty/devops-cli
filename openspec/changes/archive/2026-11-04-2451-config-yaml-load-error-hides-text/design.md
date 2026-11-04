## Context

`_read_config_file` (#1468) holds the right pattern: catch the load errors by name, read the position in a function, and raise after the `except` block. Three more paths need it, and one of them parses with ruamel.yaml.

## Decisions

- **One function, `load_yaml(parse, name=, action=, errors=)`.** The callers differ in the parser and in the first words of the message, so the function takes the parse as a callable and the message start as `action`. Rejected: one function for each parser. The logic is the same, and two functions copy it. Rejected: one function that takes the text and picks the parser. It must import ruamel.yaml, and 224 ms of import time would run at the start of every command.
- **The error list holds `ValueError`, `LookupError`, `AttributeError` and `RecursionError` by name.** PyYAML raises each one for a tag that it cannot build (`tests/config/test_config_file_that_is_not_yaml.py`). Rejected: `except Exception`. `tests/test_swallowed_failures_ratchet.py` refuses it, and it hides a bug in the code.
- **The mark is read by `getattr(exc, "problem_mark", None)`.** PyYAML and ruamel.yaml both give a mark with `line` and `column`, and no other error has the attribute. Rejected: `isinstance` with both classes. It needs the import of ruamel.yaml.
- **`OSError` goes up.** It names only the file.
- **`devops config audit-keys` keeps its behavior.** It reports an unreadable file as unaudited and exits 1. It does not stop at the first one, so it does not raise.
