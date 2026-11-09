# Tasks

## 1. Store References

- [x] 1.1 Remove the last `memory_store` identifier from test names.
  - Verification: `$ git grep -n -E "memory_store|roadmap_faults" -- src tests`

## 2. Invariant and Quality Gates

- [x] 2.1 Verify AST scans for private imports and patch sites across the 26 target test suites.
  - Verification: `$ uv run pytest tests/invariants/`
- [x] 2.2 Verify that `devops openspec check` passes.
  - Verification: `$ uv run devops openspec check`
- [x] 2.3 Run the full local quality gate suite.
  - Verification: `$ uv run devops ci`
