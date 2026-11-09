# Tasks

## 1. Resolve devops commands and flags cited in a plan

Reads: `src/devops_cli/core/command_resolver.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `openspec/specs/roadmap-stage/spec.md`. Changes: `src/devops_cli/roadmap/stage/stage_commands.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_command_citations.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_command_citations.py`, write tests covering unknown subcommands, unknown options, unknown MCP exposure table keys, known commands and options, placeholders, integration with `check_proposal`, and a test that builds this plan's own `StageProposal` and asserts that `content_problems` returns no problem. Run `uv run devops roadmap eval stage --replay` and compare the score before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_command_citations.py` fails on the base
- [x] 1.2 In `src/devops_cli/lang/en/messages.py`, add `stage_problem_command_reference` and `stage_problem_mcp_exposure_key`. In `src/devops_cli/roadmap/stage/stage_commands.py`, implement `command_citation_problems` using `resolve_devops_argv` and `CONST_MCP_EXPOSURE_TABLE`. In `src/devops_cli/roadmap/stage/stage_change.py`, wire `command_citation_problems` into `ProposalGate.CITATION`. Run `uv run devops roadmap eval stage --replay` and compare the score before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_command_citations.py` passes

## Criteria

- Group 1: The plan check SHALL resolve every `devops` command span in the Feasibility text and the task text against the real command tree.
- Group 1: The plan check SHALL accept a `devops` command span that resolves to a leaf command with valid options.
- Group 1: The plan check SHALL resolve each option flag in a cited `devops` command span against that command.
- Group 1: The plan check SHALL resolve each quoted tuple key that a plan cites against `CONST_MCP_EXPOSURE_TABLE`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
