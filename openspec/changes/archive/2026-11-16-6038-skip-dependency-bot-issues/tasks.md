# Tasks

## 1. The rows skip an issue of a tool bot

Kind: behavior. Reads: `src/devops_cli/roadmap/trust.py`, `tests/support/fakes/roadmap_store.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`, `tests/roadmap/stores/test_roadmap_store_tool_issues.py`, `tests/security/test_config_declarations.py`.

- [x] 1.1 Write failing tests: both stores list no Item and no Candidate of `dan-petty-renovate[bot]`; the rows intake, retitle, refine, alternatives, stage, implement, open and metrics name no issue of the bot and name the same issue of a person; the setting replaces the default, and an empty list skips no author
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_contract.py tests/roadmap/stores/test_roadmap_store_tool_issues.py`
- [x] 1.2 Add `roadmap.skip_authors` with its code default, add `roadmap_issues`, start `select_items` and `select_candidates` from it, and read the listing of intake through it
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_contract.py tests/roadmap/stores/test_roadmap_store_tool_issues.py tests/security/test_config_declarations.py`

## 2. Documents

Kind: other. Changes: `CONTEXT.md`, `docs/roadmap/intake.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [x] 2.1 Name the rule in the glossary entry Candidate and in the intake page, and generate the settings references
  - Verification: `$ uv run devops ci docs`
