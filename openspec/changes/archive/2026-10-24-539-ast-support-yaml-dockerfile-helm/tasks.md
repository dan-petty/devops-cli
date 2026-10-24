# Tasks

## 1. Dockerfile AST symbol extraction

- [x] 1.1 Write failing tests for Dockerfile language detection and AST symbol extraction in `tests/test_treesitter_native_symbols.py` (`uv run pytest tests/test_treesitter_native_symbols.py -k dockerfile`)
- [x] 1.2 Add `tree-sitter-dockerfile` dependency in `pyproject.toml`, map grammar in `src/devops_cli/ai/ast/engine.py`, and implement Dockerfile stage and FROM image extraction (`uv run pytest tests/test_treesitter_native_symbols.py -k dockerfile`)
- [x] 1.3 Regenerate CLI documentation with `uv run devops docs generate --sync-readme`

## 2. Helm template AST symbol extraction

- [x] 2.1 Write failing tests for Helm template language detection and define block symbol extraction in `tests/test_treesitter_native_symbols.py` (`uv run pytest tests/test_treesitter_native_symbols.py -k helm`)
- [x] 2.2 Implement balanced block parser for `.tpl` files in `src/devops_cli/ai/ast/engine.py` (`uv run pytest tests/test_treesitter_native_symbols.py -k helm`)
- [x] 2.3 Regenerate CLI documentation with `uv run devops docs generate --sync-readme`

## 3. YAML and Kubernetes manifest AST symbol extraction

- [x] 3.1 Write failing tests for YAML and Kubernetes manifest symbol extraction in `tests/test_treesitter_native_symbols.py` (`uv run pytest tests/test_treesitter_native_symbols.py -k yaml`)
- [x] 3.2 Add `tree-sitter-yaml` dependency in `pyproject.toml`, map grammar in `src/devops_cli/ai/ast/engine.py`, and implement Kubernetes resource and YAML mapping extraction (`uv run pytest tests/test_treesitter_native_symbols.py -k yaml`)
- [x] 3.3 Regenerate CLI documentation with `uv run devops docs generate --sync-readme`

## 4. Repository map and sample validation integration

- [x] 4.1 Write failing tests for Dockerfile, Helm, and YAML in multilingual repository maps and sample validation in `tests/test_review_sample_validation.py` and `tests/test_repomap.py` (`uv run pytest tests/test_review_sample_validation.py tests/test_repomap.py`)
- [x] 4.2 Update file discovery in `src/devops_cli/ai/repomap.py` and `src/devops_cli/ai/ast/graph.py` and verify sample validation (`uv run pytest tests/test_review_sample_validation.py`)
- [x] 4.3 Run complete CI test suite and quality gates (`uv run devops ci`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
