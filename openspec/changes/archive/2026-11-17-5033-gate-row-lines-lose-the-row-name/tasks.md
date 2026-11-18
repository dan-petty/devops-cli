# Tasks

## 1. Behavior

- [x] 1.1 Write the failing test for a printed row line whose name Rich would consume.
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py -k row_line`
- [x] 1.2 Build every row line with an escaped bracketed name.
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py -k row_line`

## 2. Documents

- [x] 2.1 Update the `ci-gate-rows` specification.
  - Verification: `$ uv run devops openspec check`
- [x] 2.2 Archive the change into the main specification.
  - Verification: `$ uv run devops openspec archive 5033-gate-row-lines-lose-the-row-name`
