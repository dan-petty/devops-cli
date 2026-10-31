# Tasks

## 1. Write Failing Tests First

- [x] 1.1 Add tests for `_parse_repos` in `tests/config/test_settings.py` (or existing settings test file) <!-- id: 0 -->
- [x] 1.2 Add tests for `dotted_set` top-level section, unknown top-level key, validation failure, and list field JSON string <!-- id: 1 -->

## 2. Refactor and Narrow Exceptions

- [x] 2.1 Change `except Exception:` to `except json.JSONDecodeError:` in `_parse_repos` <!-- id: 2 -->
- [x] 2.2 Decrement swallowed-failures ceiling in `tests/fixtures/swallowed_failures_ceilings.json` <!-- id: 3 -->
- [x] 2.3 Delete `_migrate_append_cache` and `append_cache` property/setter in `src/devops_cli/config/settings.py` <!-- id: 4 -->
- [x] 2.4 Update `src/devops_cli/ai/client/unified.py` to read `cache.append_cache` <!-- id: 5 -->

## 3. Verify and Validate

- [x] 3.1 Run tests and confirm all pass without patching `devops_cli` names <!-- id: 6 -->
- [x] 3.2 Run `uv run devops ci` and verify all quality gates pass <!-- id: 7 -->
