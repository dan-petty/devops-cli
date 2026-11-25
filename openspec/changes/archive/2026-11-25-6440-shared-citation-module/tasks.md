# Tasks

## 1. Shared Citation Module & Stage Gate Delegation

- [x] 1.1 Write failing tests for parsing all three citation forms, `span_hash`, local-git-first / remote-fallback commit reads, unique-only re-anchoring, permalink rendering, and `stage_change` delegation
  - Verification: `$ uv run pytest -n 0 tests/core/test_citation.py tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_citation_quote.py`
- [x] 1.2 Implement `src/devops_cli/citation.py` and delegate `src/devops_cli/roadmap/stage/stage_change.py` to `devops_cli.citation` without altering stage gate messages or outputs
  - Verification: `$ uv run pytest -n 0 tests/core/test_citation.py tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_citation_quote.py tests/roadmap/stage/test_roadmap_stage_gates.py`

## 2. Docs & Quality Gate

- [x] 2.1 Verify `openspec check`, `docs check`, and `devops ci --check`, then archive the change
  - Verification: `$ uv run devops openspec check && uv run devops docs check && uv run devops ci --check`
