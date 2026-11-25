# Tasks

## 1. Behavior

- [x] 1.1 Add failing shipped-catalog and dry-run tests asserting `spend` is removed from `disagreements` while `prometheus.cli_spend` and `prometheus.gateway_spend` remain separate facts
  - Verification: `$ uv run pytest tests/roadmap/project_review/test_review_catalog.py tests/commands/test_roadmap_review.py`
- [x] 1.2 Remove the `spend` disagreement pair from `src/devops_cli/roadmap/project_review/catalog.yaml`
  - Verification: `$ uv run pytest tests/roadmap/project_review/ tests/commands/test_roadmap_review.py`

## 2. Documents

- [x] 2.1 Update `openspec/specs/roadmap-project-review/spec.md` via OpenSpec archive and pass review docs/CI checks
  - Verification: `$ uv run devops ci --check --no-cache --only lint,format,typecheck,test-tree,docs,openspec`
