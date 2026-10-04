# Task: Agent Filing Quota Specification & Pure Quota Engine (#1153)

**Issue**: [#1153](https://github.com/dan-petty/devops-cli/issues/1153)
**Status**: Done
**Priority**: priority/p1-high
**Scope**: type/feature, priority/p1-high, scope/roadmap

## Description
Establishes the agent filing quota foundation, mathematically grounded ratio formula r(n), release credit, and allowance calculations to govern agentic issue creation across iterative cycles. Delivers Pydantic-validated roadmap configuration keys in `src/devops_cli/roadmap/config.py` and `defaults.py`, declared repository limits in `.github/roadmap.toml`, a pure mathematical module `src/devops_cli/roadmap/quota.py` avoiding I/O, declarative repository labels `source/agent` and `budget/borrowed` in `.github/labels.yml`, and governance guardrails in `AGENTS.md` and `src/devops_cli/ai/instruction_generator.py`.

## Acceptance Criteria
- [x] `RoadmapConfig` (`src/devops_cli/roadmap/config.py`) gains six quota keys (`open_issue_limit`, `throttle_start_fraction`, `overage_step_fraction`, `release_credit_base`, `release_credit_per_delivered_item`, `release_item_target`) with defaults in `src/devops_cli/config/defaults.py` and Pydantic constraints.
- [x] `.github/roadmap.toml` declares all six keys with one comment line each, parsed via `read_roadmap_config`.
- [x] Tests in `tests/test_roadmap_config.py` cover defaults, declared file, fraction boundary rejections, and unknown key rejection.
- [x] Pure module `src/devops_cli/roadmap/quota.py` exposes `ratio(n, config)`, `release_credit(delivered, config)`, and `allowance(n, delivered, closures, config)` with exact stdlib arithmetic.
- [x] Tests in `tests/test_roadmap_quota.py` assert `r(n)` curve values (150, 160, 180, 200, 250, 289), credit calculation (0, 30, 70 delivered), and allowance figures (`allowance(250, 70, 20) = 60`, `allowance(280, 70, 20) = 57`, and infinite allowance when `r(n) == 0`).
- [x] Added `source/agent` and `budget/borrowed` labels with colors to `.github/labels.yml`.
- [x] Updated `AGENTS.md` filing rules and mirrored them in `devops_roadmap_governance_block` in `src/devops_cli/ai/instruction_generator.py`.
- [x] Updated `tests/test_instruction_generator.py` asserting `source/agent`, `budget/borrowed`, and `open_issue_limit` in the template.
- [x] Authored changelog fragment `changelog.d/1153.md`.
- [x] All 10 CI quality gates pass via `uv run devops ci`.

## Deliverables
- [x] `src/devops_cli/config/defaults.py`: Quota defaults.
- [x] `src/devops_cli/roadmap/config.py`: Quota configuration keys and field constraints.
- [x] `.github/roadmap.toml`: Declared quota keys.
- [x] `src/devops_cli/roadmap/quota.py`: Pure quota ratio, credit, and allowance engine.
- [x] `.github/labels.yml`: `source/agent` and `budget/borrowed` label definitions.
- [x] `AGENTS.md`: Filing quota governance rules.
- [x] `src/devops_cli/ai/instruction_generator.py`: Mirrored roadmap governance block.
- [x] `tests/test_roadmap_config.py`: Quota config tests.
- [x] `tests/test_roadmap_quota.py`: Pure quota unit test suite.
- [x] `tests/test_instruction_generator.py`: Generator assertions.
- [x] `changelog.d/1153.md`: Changelog fragment.
- [x] `docs/agent/tasks/task-1153-agent-filing-quota.md`: Task tracking file.
