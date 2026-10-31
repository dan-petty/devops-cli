# Tasks

## 1. Remove mock detection and internal subprocess aliases

- [x] Add failing test asserting zero mock-detection logic in `src/`: `uv run pytest tests/invariants/test_source_tree.py -k test_no_mock_imports_in_src`
- [x] Remove `NonCallableMock` check in `_is_scannable_manifest` in `src/devops_cli/ai/review/pipeline.py`: `uv run pytest tests/ai/review/test_review_static_analyzers.py`
- [x] Replace `_run_subprocess` alias with `run_subprocess` in `src/devops_cli/ai/review/runner.py`: `uv run pytest tests/ai/review/test_review_runner.py`
- [x] Route review runner and symbol delta git commands through `process_fake`: `uv run pytest tests/ai/review/test_review_runner.py tests/ai/review/test_review_symbol_delta.py`
- [x] Synchronize CLI documentation: `uv run devops docs generate --sync-readme`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
