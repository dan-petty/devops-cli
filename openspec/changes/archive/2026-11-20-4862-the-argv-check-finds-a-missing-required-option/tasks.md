# Tasks

## 1. Find a missing required parameter in a command line

Kind: behavior. Reads: `src/devops_cli/core/command_resolver.py`, `src/devops_cli/lang/en/messages.py`, `tests/core/test_docs_command_resolver.py`, `tests/roadmap/stage/test_roadmap_stage_command_citations.py`. Changes: `src/devops_cli/core/command_resolver.py`, `src/devops_cli/lang/en/messages.py`, `tests/core/test_docs_command_resolver.py`, `tests/roadmap/stage/test_roadmap_stage_command_citations.py`.

- [x] 1.1 In `tests/core/test_docs_command_resolver.py`, `test_resolver_reports_missing_required_option`, `test_resolver_reports_missing_required_argument`, `test_resolver_reports_a_missing_variadic_argument`, `test_resolver_skips_bare_command_mention`, `test_resolver_treats_placeholder_as_argument_not_option` and `test_a_required_option_is_given_as_click_parses_it` assert the scenarios of `docs-command-lines`. `test_a_finding_describes_itself` asserts the new message. In `tests/roadmap/stage/test_roadmap_stage_command_citations.py`, `test_plan_with_missing_required_option_is_refused` asserts that the plan check refuses `devops pr describe 1`
  - Verification: `$ uv run devops ci test tests/core/test_docs_command_resolver.py tests/roadmap/stage/test_roadmap_stage_command_citations.py` fails on the base
- [x] 1.2 Add `MISSING_REQUIRED` to `CommandReferenceDefect` and `argv_missing_required` to `src/devops_cli/lang/en/messages.py`. Add `_missing_required` and `_parameter_token` to `src/devops_cli/core/command_resolver.py`, and let `_parse` report a missing parameter on the fallback path before an extra argument
  - Verification: `$ uv run devops ci test tests/core/test_docs_command_resolver.py tests/roadmap/stage/test_roadmap_stage_command_citations.py` passes

## 2. Correct the command lines that the check finds

Kind: documents. Changes: `.agents/skills/devops-pr-ci/SKILL.md`, `.claude/skills/devops-pr-ci/SKILL.md`, `.kilocode/skills/devops-pr-ci/SKILL.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, `docs/roadmap/implement.md`, `docs/roadmap/onboard.md`, `k8s/README.md`.

- [x] 2.1 Add `--summary "<summary>"` to the `devops pr describe` line 26 of the three devops-pr-ci skill files
  - Verification: `$ uv run devops docs check`
- [x] 2.2 Correct the lines that the proposal lists in `docs/` and `k8s/README.md`
  - Verification: `$ uv run devops docs check`
