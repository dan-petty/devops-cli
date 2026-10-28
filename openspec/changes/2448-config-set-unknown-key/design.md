# Design

## Context

`devops config set` resolves its value first: `_value_or_prompt` asks for a credential at a hidden prompt, or exits 2 for any other key without a VALUE, and `_secret_from_file` reads `--from-file`. Then it loads the settings and calls `dotted_set`, which walks the sections of the key and raises `ConfigurationError` when a part names no field. So the only check that a key exists comes after the value. `devops config get` finds an unknown key when `operator.attrgetter` raises `AttributeError`.

## Decisions

### The known keys come from the settings model and the credential set

`_field_keys` walks `Settings.model_fields`. A field whose type is a `BaseModel` subclass is a section, and the walk goes into it; any other field holds a value and gives its dotted key. The known keys are these keys and the credential set `_SECRET_FIELDS`, because some credentials, such as `grafana.token`, have no settings field and `dotted_set` stores them in the keyring by name. The walk has about 200 steps and a command does it once or twice, so no cache keeps the set: the hermetic floor would have to reset each cache in `src`. `is_config_key` maps the `otel.<field>` name to `telemetry.<field>` first, as `dotted_get` and `dotted_set` do.

### The check comes first in devops config set

`set` calls `is_config_key` before it resolves the value. So an unknown key exits 1 before the prompt, before it reads a file or stdin, and before it loads the settings. A known key goes on as before: a credential with no VALUE gets the prompt, and any other key with no VALUE exits 2.

### devops config get keeps its own lookup

`get` still finds an unknown key through `attrgetter`, and prints the same two lines as `set` when the lookup fails. The check of `set` would refuse a section, but `get` prints a section today, so `get` does not call it.

### The similar keys come from difflib

`similar_config_keys` gives `difflib.get_close_matches` the key, with the `otel.` name mapped, and the known keys, with the defaults of three matches and a cutoff of 0.6. The command prints the line only when there is a match.

## Rejected alternatives

- Load the settings and try `dotted_get` before the prompt, as `get` does. `attrgetter` also resolves a section and a method of a model, such as `ai.model_dump`, and it does not find the credentials that have no settings field, such as `grafana.token`. The known-key tests of `tests/config/test_config_keys.py` hold all three cases.
- Read `CONFIG_OPTIONS` or `OPTION_TO_ENV_VAR` from `config/options.py` and `config/env.py`. Both are hand-written lists. `CONFIG_OPTIONS` has no reader outside its module, and #2444 deletes both, so the change would read a list that goes away.
- Raise a `ConfigurationError` from the settings module and report it with `exit_on_error`. That prints the message with the error prefix, so it is not the message of `devops config get`, which the issue asks for.
- Keep the specific `Cannot set top-level section` message of `dotted_set` for a section on the command line. A section is not a key that `devops config set` takes, and the message of an unknown key names it. `dotted_set` keeps the guard for the callers in code.
