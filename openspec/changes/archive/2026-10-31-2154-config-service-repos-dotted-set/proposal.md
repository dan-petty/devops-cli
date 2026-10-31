# Change: Cover Service Repo List Parser and Top-Level Dotted Set, Retire Append Cache Shim

## Why

Some branches of `config/settings.py` that read user input have no test coverage. In `ServiceConfig._parse_repos`, a broad `except Exception` swallows all exceptions silently instead of only `json.JSONDecodeError`. In `dotted_set`, the code path for top-level keys (setting a section directly, an unknown top-level key, and validation failure) has no tests. Setting list fields with JSON list strings in `_coerce_setting_value` is not tested through `dotted_set`. Furthermore, `_migrate_append_cache` and the `append_cache` property are shims for backwards compatibility; devops-cli keeps no backward compatibility before 1.0.0.

## Feasibility

Confirmed against the real system:
- `src/devops_cli/config/settings.py:924-951`: `_parse_repos` catches `Exception` at line 948 when parsing a single-element list. Changing this to `json.JSONDecodeError` narrows the exception type to valid JSON decode errors.
- `src/devops_cli/config/settings.py:1767-1794`: `dotted_set` contains branches for top-level section assignments, missing fields, and Pydantic validation errors.
- `src/devops_cli/config/settings.py:1746-1756`: `_coerce_setting_value` parses string inputs starting with `[` and ending with `]` into lists using `_json_list`.
- `src/devops_cli/config/settings.py:700-722`: `_migrate_append_cache` and `append_cache` property/setter exist and can be removed.
- `src/devops_cli/ai/client/unified.py:198-202`: Reads `config.append_cache` or `config.cache.append_cache`. Removing `append_cache` from `AIConfig` allows reading `cache.append_cache` directly.
- `tests/fixtures/swallowed_failures_ceilings.json:73`: Records a ceiling of 2 for `src/devops_cli/config/settings.py`. Narrows `except Exception` so the ceiling decreases to 1.

## What Changes

1. Write tests for `_parse_repos` covering:
   - a JSON list string (e.g. `'["org/repo1", "org/repo2"]'`),
   - a comma-separated string (e.g. `"org/repo1, org/repo2"`),
   - an empty string (`""`),
   - a single-item list holding a JSON list (e.g. `['["org/repo1"]']`),
   - a single-item list holding invalid JSON (e.g. `['[broken']`).
2. Write tests for `dotted_set` covering:
   - assigning a value directly to a top-level section (e.g. `ai = "foo"`),
   - setting an unknown top-level key,
   - setting a top-level field with a value that fails validation,
   - setting a list field using a JSON list string.
3. In `src/devops_cli/config/settings.py`:
   - Replace `except Exception:` with `except json.JSONDecodeError:` in `_parse_repos`.
   - Remove `_migrate_append_cache` and `append_cache` property/setter from `AIConfig`.
4. In `src/devops_cli/ai/client/unified.py`:
   - Read `getattr(config.cache, "append_cache", False)` instead of `config.append_cache`.
5. In `tests/fixtures/swallowed_failures_ceilings.json`:
   - Decrement the ceiling for `src/devops_cli/config/settings.py` from 2 to 1.
