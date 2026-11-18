# Tasks

## 1. Behavior

- [x] 1.1 Add the `test-tree` check that fails on an unscoped image build cache entry.
  - Verification: `$ uv run python -c "from tests.gate.tree import main; raise SystemExit(main())"`
- [x] 1.2 Give each image build of the three workflows its target scope.
  - Verification: `$ uv run python -c "from tests.gate.tree import main; raise SystemExit(main())"`

## 2. Documents

- [x] 2.1 State the scopes in the Image paragraph of `docs/CLUSTER.md`.
  - Verification: `$ uv run devops ci docs`
- [x] 2.2 Update the `container-image-layers` specification.
  - Verification: `$ uv run devops openspec check`
- [x] 2.3 Archive the change into the main specification.
  - Verification: `$ uv run devops openspec archive 4928-image-cache-scope`
