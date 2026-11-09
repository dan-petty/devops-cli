# Design

## Decisions
- **Reuse `resolve_devops_argv` for command checking**: Parse the cited command lines with `resolve_devops_argv` in `src/devops_cli/core/command_resolver.py`. It parses the full command line, reports unknown commands, unknown options, or unexpected arguments, and executes nothing.
- **Run in `check_proposal` under `ProposalGate.CITATION`**: Put the command citation check in `check_proposal` inside `src/devops_cli/roadmap/stage/stage_change.py` as part of the citation gate. One rule serves the stage job, `devops roadmap plan-check`, and the stage evaluation replay.
- **Keep check out of `devops openspec check`**: Keep it a non-goal for `devops openspec check`. `devops openspec check` validates an OpenSpec change folder and does not have the Feasibility or task text structure of a stage proposal.
- **Match quoted tuples against `CONST_MCP_EXPOSURE_TABLE`**: Check exact tuple keys in Feasibility and task texts against `CONST_MCP_EXPOSURE_TABLE` to prevent invalid exposure keys like `("ai", "ast-graph")`.

## Rejected alternatives
- **Call `resolve_click_command` directly**: Rejected because it resolves a command tuple but does not parse option flags or report unknown options.
- **Build a new parser**: Rejected because it duplicates existing resolution logic and increases maintenance overhead.
- **Run only in `devops roadmap plan-check`**: Rejected because the stage job and replay would accept bad plans.
