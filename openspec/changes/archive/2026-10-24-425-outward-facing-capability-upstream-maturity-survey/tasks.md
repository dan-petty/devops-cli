# Tasks

## 1. Upstream dependency maturity survey

- [x] 1.1 Write failing tests for dependency inspection and mechanical signals in tests/test_survey_dependencies.py (`uv run pytest tests/test_survey_dependencies.py`)
- [x] 1.2 Implement dependency models, PyPI metadata parsing, and upstream GitHub signals collection in src/devops_cli/survey/dependencies.py (`uv run pytest tests/test_survey_dependencies.py`)
- [x] 1.3 Regenerate CLI documentation with `uv run devops docs generate --sync-readme`

## 2. Comparable tools capability comparison

- [x] 2.1 Write failing tests for capability configuration, citation requirements, and unknown-status enforcement in tests/test_survey_capabilities.py (`uv run pytest tests/test_survey_capabilities.py`)
- [x] 2.2 Implement capability parsing, gap detection, and citation validation in src/devops_cli/survey/capabilities.py (`uv run pytest tests/test_survey_capabilities.py`)
- [x] 2.3 Regenerate CLI documentation with `uv run devops docs generate --sync-readme`

## 3. CLI command, report generation, and roadmap intake

- [x] 3.1 Write failing tests for the survey CLI command, JSON/table report output, and roadmap candidate hand-off in tests/test_survey_cmd.py (`uv run pytest tests/test_survey_cmd.py`)
- [x] 3.2 Implement the survey command in src/devops_cli/commands/survey.py with candidate emission to intake (`uv run pytest tests/test_survey_cmd.py`)
- [x] 3.3 Create default configuration in .devops/survey.toml and register command help and messages in language catalog (`uv run pytest tests/test_survey_cmd.py`)
- [x] 3.4 Regenerate CLI documentation with `uv run devops docs generate --sync-readme`

## 4. Verification and quality gates

- [x] 4.1 Write task file docs/agent/tasks/task-425-outward-facing-capability-upstream-maturity-survey.md and verify task contracts (`uv run pytest tests/test_agent_task_files.py`)
- [x] 4.2 Run complete CI test suite and quality gates (`uv run devops ci`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
