## Why

Generated documentation fills pull request diffs and reaches model review on every run because `.gitattributes` only marks two of the 11 generated globs (with bare `linguist-generated` rather than `linguist-generated=true`) and `CONST_REVIEW_ROUTED_PATH_PATTERNS` only lists `docs/commands/*.md` and `docs/CLI_REFERENCE.md`. In addition, no contributor doc explains how to resolve a rebase conflict on a generated file (Closes #4888).

## What Changes

- Set `linguist-generated=true` in `.gitattributes` for every glob in the `generated` class of `CONST_DOCS_INVENTORY`, keeping all other tracked Markdown files `unspecified`.
- Update `is_secret_scan_only` (`src/devops_cli/review/targets.py`) to read `CONST_DOCS_INVENTORY[CONST_DOCS_CLASS_GENERATED]` at call time and remove `"docs/commands/*.md"` and `"docs/CLI_REFERENCE.md"` from `CONST_REVIEW_ROUTED_PATH_PATTERNS`.
- Add a generated-attributes check helper and tests covering `.gitattributes` entries, `git check-attr linguist-generated`, `is_secret_scan_only`, `CONST_REVIEW_ROUTED_PATH_PATTERNS`, and `CONTRIBUTING.md`.
- Add the generated-file rebase conflict procedure to the Documentation Synchronization bullet in `CONTRIBUTING.md`.

## Capabilities

### Modified Capabilities

- `docs-cli-reference`: Mark all generated documentation globs with `linguist-generated=true`, route all generated docs via `CONST_DOCS_INVENTORY` in `is_secret_scan_only`, and document the rebase conflict recovery step in `CONTRIBUTING.md`.

## Impact

- `.gitattributes`
- `src/devops_cli/config/constants.py`
- `src/devops_cli/docs/inventory.py`
- `src/devops_cli/review/targets.py`
- `CONTRIBUTING.md`
- `tests/docs/test_docs_inventory.py` and `tests/review/test_review_diff.py`
