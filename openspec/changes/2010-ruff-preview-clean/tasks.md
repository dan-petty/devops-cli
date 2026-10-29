# Tasks

## 1. The code that Ruff preview flags is rewritten

- [x] Record the 87 findings on origin/main with the preview setup of #1876
  - Verification: `uv run ruff check --preview --config 'lint.explicit-preview-rules = true' --extend-select PLR1702 --config 'lint.pylint.max-nested-blocks = 5' .`
- [x] Import the exported names of the 5 lazy-export modules under `TYPE_CHECKING`, from each module's own export map
  - Verification: `uv run mypy src` and `uv run devops ci test tests/test_cli_startup_imports.py tests/test_public_export_surface.py tests/test_ai_init.py`
- [x] Rewrite `AbstractToolset` and `FunctionToolset` with PEP 695 type parameters, and delete the unused `TypeVar`
  - Verification: `uv run devops ci test tests/test_pydantic_ai_toolsets.py`
- [x] Write the micro sign as `\u00b5` in `scalars.py` and its test, and delete the unused import in `tests/test_fast_dispatch.py`
  - Verification: `uv run devops ci test tests/test_output.py tests/test_fast_dispatch.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2010-ruff-preview-clean`

## Workflow follow-up

- #1876 turns on preview, enables `PLR1702` and deletes the structural-invariants hook.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
