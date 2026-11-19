# Tasks

## 1. Core Resolver Updates
- [x] 1.1 Add `argv_missing_required` message in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/core/test_docs_command_resolver.py`
- [x] 1.2 Implement `MISSING_REQUIRED` defect in `src/devops_cli/core/command_resolver.py`
  - Verification: `$ uv run devops ci test tests/core/test_docs_command_resolver.py`

## 2. Documentation and Skill Corrections
- [x] 2.1 Update skill files at line 26 with `--summary` option
  - Verification: `$ uv run devops docs check`
- [x] 2.2 Correct documented command lines in `docs/` and `k8s/README.md`
  - Verification: `$ uv run devops docs check`

## 3. Test Coverage
- [x] 3.1 Add resolver unit tests for options, arguments, placeholders, and bare mentions
  - Verification: `$ uv run devops ci test tests/core/test_docs_command_resolver.py`
- [x] 3.2 Add stage plan test for missing required option
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_command_citations.py`
