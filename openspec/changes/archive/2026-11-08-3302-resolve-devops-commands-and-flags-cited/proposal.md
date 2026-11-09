# Proposal: #3302

## Why
Issue #3302: The plan check accepts `devops` commands, option flags and MCP exposure keys that do not exist. A plan can cite `uv run devops ai ast-graph --help`, `uv run devops gh pages verify --root_dir .`, or `("ai", "ast-graph")`. The check must resolve cited command spans and options against the real command tree, resolve quoted exposure keys against `CONST_MCP_EXPOSURE_TABLE`, and report unknown names.

## What Changes
- Add `stage_commands.py` with `command_citation_problems` to validate command spans, options and quoted MCP exposure keys cited in Feasibility and task texts.
- Add `stage_problem_command_reference` and `stage_problem_mcp_exposure_key` messages in `src/devops_cli/lang/en/messages.py`.
- Include `command_citation_problems` under `ProposalGate.CITATION` in `check_gates` within `src/devops_cli/roadmap/stage/stage_change.py`.

## Capabilities
### roadmap-stage
Add requirements to resolve cited command spans, option flags and MCP exposure keys in stage proposals.

## Impact
- `devops roadmap plan-check`, the stage job, and stage eval replay will reject stage proposals that cite nonexistent commands, subcommands, options, or MCP exposure table keys.
- No changes to CLI behavior or public APIs.

## Feasibility
- `resolve_devops_argv` in `src/devops_cli/core/command_resolver.py` resolves arbitrary `devops` argv tokens and reports `unknown_command`, `unknown_option`, and `unexpected_argument`.
- `CONST_MCP_EXPOSURE_TABLE` in `src/devops_cli/config/constants.py` contains the authoritative list of valid MCP tool exposure tuples.
- The `citation` gate in `check_gates` (`src/devops_cli/roadmap/stage/stage_change.py`) already runs on all stage proposals across plan-check, stage evaluation, and roadmap stage runs.

## Existing Tool Considered
`resolve_devops_argv` in `src/devops_cli/core/command_resolver.py` and `CONST_MCP_EXPOSURE_TABLE` in `src/devops_cli/config/constants.py` cover the need. Reusing the existing parser avoids duplicating Click command resolution. Cost to build: about 5,000 tokens and 30 minutes.
