# Tasks

## 1. Walk the tree once and skip ignored folders (behavior)

- [x] 1.1 Write a failing test: the build lists no ignored folder and no `.git`, and indexes only the file outside them
  - Verification: `$ uv run devops ci test tests/ai/ast/test_treesitter_engine.py`
- [x] 1.2 Replace the `rglob` loop for each extension with one `os.scandir` walk that keeps the order of `Path.rglob` and does not go into an ignored folder
  - Verification: `$ uv run devops ci test tests/ai/ast/test_treesitter_engine.py`

## 2. Search a body only for the names that it holds (refactor that keeps behavior)

- [x] 2.1 Add a test: a body that holds the name of a function, but does not call it, links nothing
- [x] 2.2 Test that the body holds the name before the call regex runs
  - Verification: `$ uv run devops ci test tests/ai/ast/test_treesitter_engine.py`

## 3. Run the dry-run case on a small folder (test-only edit)

- [x] 3.1 Give the dry-run case of `ai ast graph` the option `--dir src/devops_cli/ai/ast`
  - Verification: `$ uv run devops ci test tests/commands/test_ai_local_dry_run.py`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
