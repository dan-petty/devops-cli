# Proposal

## Why

Issue #2448: `devops config set <key>` with no VALUE checks only whether the key is a credential. A key that the settings do not know gets the message of a known key that is not a credential, `<key> needs a VALUE; only a credential may be typed at a hidden prompt.`, and exits 2. With a VALUE, the same key fails later, in the walk of `dotted_set`, with `Failed to set '<key>': Unknown configuration key '<key>'.`. With `--from-file`, it gets `<key> is not a credential` and exits 2. None of these messages says that the key is unknown, so a person who types a credential name that this install does not know, such as `tavily.api_key` after #2410 renamed it to `firecrawl.api_key`, reads it as "this key is not a credential".

## What Changes

- `devops config set` checks the key first. A key that names no settings field with a value and no credential exits 1 with `Unknown config key: '<key>'`, the message of `devops config get`. The check comes before the hidden prompt, the read of `--from-file` and the load of the settings, so nothing is stored.
- A second line names the known keys with a similar name, the nearest first, when there are such keys: `Known keys with a similar name: firecrawl.api_key, ai.api_key, qdrant.api_key`. `devops config get` gives the same lines for a key that it cannot find.
- The known keys are the fields of the `Settings` model that hold a value, at any depth, and the credentials. A section, such as `ai` or `ai.tasks.chat`, holds no value, so `devops config set` reports it as an unknown key.
- The two messages move to `src/devops_cli/lang/en/messages.py`. `docs/CONFIGURATION.md` describes the check.
- The messages and the exit code of a command are observable behavior, so the change carries a spec delta for `config-commands`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: `devops config set` refuses an unknown key before it asks for a value, and `devops config set` and `devops config get` name the known keys with a similar name.

## Impact

- `src/devops_cli/config/settings.py`: `is_config_key` and `similar_config_keys`, which read the fields of the `Settings` model and the credential set.
- `src/devops_cli/commands/config.py`: `set` checks the key first; `get` and `set` print the same two lines for an unknown key.
- `src/devops_cli/lang/en/messages.py`: the two messages.
- `src/devops_cli/docs/generator.py` and the generated `docs/CONFIGURATION.md`.
- Tests: `tests/config/test_config_keys.py` and `tests/commands/test_config.py`.

## Feasibility

- Reproduced on `origin/main` (95eb8b68), Python 3.14.10 and pydantic 2.13.5, with the CLI tests that this change adds. They run `devops config set` in process with the `cli` fixture, an isolated `DEVOPS_CLI_CONFIG` and the fake keyring. `devops config set no.such_key` exits 2 with `no.such_key needs a VALUE; only a credential may be typed at a hidden prompt.`. `devops config set tavily.api_key example-value` exits 1 with `Failed to set 'tavily.api_key': Unknown configuration key 'tavily.api_key'.`. `devops config set firecrawl.apikey --from-file -` exits 2 with the usage error `firecrawl.apikey is not a credential`. `devops config get firecrawl.apikey` exits 1 with `Unknown config key: 'firecrawl.apikey'` alone.
- The issue says that the message with a VALUE is the text of an `AttributeError`. On `origin/main` it is the text of the `ConfigurationError` that `dotted_set` raises for a section that does not exist. `ConfigurationError` is a `ValueError`, so the `except (AttributeError, ValueError)` of `set` prints it after `Failed to set`. The rest of the premise holds.
- pydantic 2.13.5 gives each field of a model in `model_fields`, with the type of the field in `FieldInfo.annotation`. A section field has a `BaseModel` subclass as its type, also when its default comes from `default_factory`, such as `service.github_app`. The walk of these fields gives 192 keys, and the credential set adds 10 credentials that have no settings field, such as `grafana.token` and `service.github_app.private_key`.
- The Python documentation of `difflib.get_close_matches(word, possibilities, n=3, cutoff=0.6)` says that it returns a list of the best matches, the most similar first. On `origin/main` it gives `firecrawl.api_key`, `ai.api_key` and `qdrant.api_key` for `firecrawl.apikey`, and nothing for `no.such_key`.
- Open issue #2444 derives the variable, option and secret registries from the settings fields. This change adds no registry: it reads the `Settings` model and the credential set `_SECRET_FIELDS`, which `config get`, `config set` and `dotted_set` already read. When #2444 derives the credential set from the credential table, `_config_keys` reads the derived set in its one line.

## Existing Tool Considered

- The standard library `difflib.get_close_matches` finds the similar keys. pydantic's `model_fields` gives the fields of the settings. No new dependency, and no list of keys is written by hand.
- `CONFIG_OPTIONS` in `src/devops_cli/config/options.py` is a hand-written list of keys with no reader outside its module, and #2444 deletes it, so the change does not read it.
- The change deletes the inline message string of `devops config get`, which moves to `messages.py`.
