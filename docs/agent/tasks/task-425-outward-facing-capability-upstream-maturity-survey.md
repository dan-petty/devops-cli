# Task: Outward-Facing Capability & Upstream Maturity Survey (#425)

**Issue**: [#425](https://github.com/dan-petty/devops-cli/issues/425)
**Scope**: scope/cli
**Feasibility**: Verified pyproject.toml runtime dependencies against uv.lock and importlib.metadata for offline maturity scoring. Verified capability config parsing against .devops/survey.toml. Verified intake candidate integration against InMemoryRoadmapStore.

## Description
This deliverable introduces an outward-facing capability and upstream maturity survey command: `devops survey`. It enables devops-cli to mechanically score the maintenance health of pinned runtime dependencies and compare capabilities against configured peer tools (such as gh, k9s, and glab).

Key capabilities implemented:
1. **Upstream Maturity Scoring**: Inspects pinned runtime dependencies from `pyproject.toml` and `uv.lock` or `importlib.metadata`. Evaluates release cadence, last release date, license expression, and calculates an overall maturity score.
2. **Capability Comparison**: Compares configured capabilities in `.devops/survey.toml` against comparable tools. Enforces epistemic honesty: unassessed capabilities for comparable tools report as `unknown`, never `absent`. Every capability row carries a citation.
3. **Capability Gap Identification**: Automatically identifies gaps where a capability is present in a comparable tool but absent in devops-cli.
4. **Roadmap Intake Integration**: When run with `--emit-candidates`, files capability gaps into the roadmap intake system as `NewCandidate` items.
5. **Machine-Readable CLI Output**: Provides `devops survey` with `--format table|json`, `--dependencies-only`, `--capabilities-only`, and dry-run candidate emission.

## Acceptance Criteria
- [x] Mechanical maturity scoring evaluates pinned runtime dependencies for release cadence, date, license, and health score.
- [x] Capability matrix compares devops-cli features against configured comparable tools in `.devops/survey.toml`.
- [x] Every capability claim about a comparable tool carries a citation.
- [x] Unassessed capabilities for comparable tools report as `unknown`, never `absent`.
- [x] Identified capability gaps can be emitted to roadmap intake as candidate backlog items.
- [x] CLI command `devops survey` supports `--json`, `--format`, `--dependencies-only`, `--capabilities-only`, and `--emit-candidates`.
- [x] Unit test suite covers dependency scoring, capability comparisons, CLI command options, and intake integration.
- [x] OpenSpec change proposal, design, specs, and tasks created and validated.
- [x] CLI documentation and README updated with `devops survey`.

## Deliverables
- [x] `src/devops_cli/survey/models.py` with survey data models.
- [x] `src/devops_cli/survey/dependencies.py` with dependency maturity scoring logic.
- [x] `src/devops_cli/survey/capabilities.py` with capability comparison and gap detection.
- [x] `src/devops_cli/survey/intake.py` with roadmap intake candidate bridge.
- [x] `src/devops_cli/commands/survey.py` CLI command implementation.
- [x] `.devops/survey.toml` survey configuration file.
- [x] `tests/test_survey_dependencies.py`, `tests/test_survey_capabilities.py`, `tests/test_survey_cmd.py` tests.
- [x] OpenSpec change proposal `openspec/changes/425-outward-facing-capability-upstream-maturity-survey/`.
- [x] Task file `docs/agent/tasks/task-425-outward-facing-capability-upstream-maturity-survey.md`.
