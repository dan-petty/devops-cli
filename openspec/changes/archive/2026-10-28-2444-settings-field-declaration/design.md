# Design

## Context

#1000 asks for one declaration of each setting. Part 1 (#2444) moves the declaration onto the settings fields and derives every list from it. Part 2 (#2445) moves the resolution order into pydantic-settings sources, and part 3 (#2447) holds field-backed defaults inside `config/`.

## Decisions

### The variable of a setting follows one rule, with a declared segment

The variable is `DEVOPS_CLI_` and the dotted key in upper case, with `_` for `.`. A `Variable(segment=...)` marker on a section field replaces that field's name in the variables under it. Only `ai.tasks` uses it (`TASK`).

Rejected: one marker with an explicit name on each field. It writes the name 85 times beside a key that already gives it, and a name can drift from its key again.

Rejected: rename the 17 task variables to `AI_TASKS_`. The names are in `k8s/README.md`, `docs/SELF_IMPROVEMENT.md`, the knowledge base and an archived spec, and #1000 requires that the set of names does not change.

### A section model that several fields share is bound at the field that holds it

`AITaskOverride` holds the fields of six tasks. Four tasks bind `provider`, `model`, `reasoning_effort` and `ollama_urls`, and only `embedding` binds `timeout`. A marker on the shared model cannot tell them apart, so each task field of `AITasksConfig` names its bound fields with `Variable(fields=...)`.

Rejected: a marker on each field of `AITaskOverride`. It gave `verification` and `compose` 8 variables that they never had; the snapshot test found them.

### A credential is a `CREDENTIALS` entry, not a settings field

10 of the 15 credentials are not settings fields: the keyring, Vault or a variable holds them, and the config file never does. A field for each would let `config.yaml` hold them and `save_settings` write them. The entry names the key, the description, the other variables, whether the file may hold it, and the keyring name when it differs. The vault name is the keyring name, as it was for all 15.

### Every declared setting has a variable

An option that code reads and that had no variable gets one by the rule (10 options). One kind of setting is simpler for `config show`, `config env` and the docs than two kinds. No manifest, devcontainer or document sets one of the 10 names (`git grep`). An option that no code reads gets no variable: `telemetry.logfire`, `cloudflare.access.enabled` and `cloudflare.access.idp` stay unmarked, and #2457 decides them.

### `config show` lists the declared settings and has a machine-readable form

It prints every setting that a variable sets and every credential, sorted by key, in place of a hand-picked 29 rows. `--format` and `--json` follow `config env`, so a test reads its rows as data and a script can too.

### The walk is cached

A walk over `Settings.model_fields` takes about 0.5 ms, and `load_settings` reads it twice. `_settings_declarations` is cached, and `reset_declarations_cache` joins the floor's reset table, as every cached function in `src` must.

## Risks

- A variable that a shell exports for one of the 10 options now changes the setting. No file in the repository sets one.
