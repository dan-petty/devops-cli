# Tasks

## 1. Break kind_of collision by pull request title prefix

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_pull.py`, `tests/roadmap/test_roadmap_draft_readiness.py`. Changes: `src/devops_cli/roadmap/implement/implement_pull.py`, `tests/roadmap/test_roadmap_draft_readiness.py`.

- [x] 1.1 Add failing tests in `tests/roadmap/test_roadmap_draft_readiness.py` covering collision resolution for `kind_of`: stage plan title returns `DraftKind.STAGE_PLAN`, implement title returns `DraftKind.IMPLEMENT`, and missing title defaults to `DraftKind.IMPLEMENT`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py` fails on the base
- [x] 1.2 Update `kind_of` in `src/devops_cli/roadmap/implement/implement_pull.py` to accept optional `title` and return `DraftKind.STAGE_PLAN` on collision when the title starts with `docs(openspec): plan`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py` passes

## 2. Pass pull request title in read_draft and stage_ready

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `src/devops_cli/roadmap/steps/fix_checks.py`, `tests/roadmap/test_roadmap_draft_readiness.py`. Changes: `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `src/devops_cli/roadmap/steps/fix_checks.py`, `tests/roadmap/test_roadmap_draft_readiness.py`.

- [x] 2.1 Add failing tests in `tests/roadmap/test_roadmap_draft_readiness.py` for `read_draft` and `draft_readiness` with colliding pull request numbers: verify stage plan classification and acceptance of unticked tasks
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py` fails on the base
- [x] 2.2 Update `read_draft` in `src/devops_cli/roadmap/implement/implement_pull.py`, `_settle` in `src/devops_cli/roadmap/stage/stage_ready.py`, and callers in `src/devops_cli/roadmap/steps/fix_checks.py` to pass the title to `kind_of`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py` passes
