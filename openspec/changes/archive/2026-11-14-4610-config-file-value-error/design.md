# Design

## Context

`_settings_from` turns a refused variable into `ConfigurationError` through `_variable_error`. `load_settings` handles unknown keys. A field validator on a config-file value reaches neither.

## Goals

- One line with the file, the setting and the reason.
- No pydantic URL and no traceback.

## Decisions

- **Convert in `load_settings`.** It holds the layers and the unknown-key path.
- **The longest declared prefix.** A prefix that one of the two mappings holds names a settable key, not a list index.
- **The file that holds the key.** The project file wins when it holds the key, else the global file.
- **Skip an unmatched error.** A model-level error can come from a variable, and the variable error already names it.

## Risks

- A cross-field error whose location is a config key is named as a file error. The reason text still states the rule.

## Tests

- A refused effort value and a duplicate repository give one `ConfigurationError` with the key.
- The CLI exits 1 with no traceback.
