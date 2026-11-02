# Design

## Decisions

- **Put the command in `src/devops_cli/commands/roadmap_eval_intake.py` and register it on `eval_app`.**: It matches the stage, implement and verify modules, and it keeps every evaluation in one group.
- **Remove `devops roadmap intake-eval` with no alias and no shim.**: The project is before 1.0.0 and keeps no compatibility shim, and an alias keeps the second place for an evaluation that the change removes.
- **Replace the MCP exclusion entry `("roadmap", "intake-eval")` with `("roadmap", "eval", "intake")`.**: `test_all_cli_commands_are_either_exposed_or_excluded` fails when a command is neither exposed nor excluded, and every command of the eval group is excluded.
- **Scope the search for the old name to `src/`, `tests/`, `docs/` and `README.md`.**: The change folder of this item and the archived changes name the old command in a MUST NOT line and in the record of a past delivery, and `CHANGELOG.md` is the record of a release.
- **Regenerate the command matrix and the command reference instead of editing them by hand.**: Both come from the live CLI, and `devops ci docs` refuses a hand edit that drifts from it.
- **Change no workflow or manifest.**: No CI job runs an eval command; `README.md` states that the eval group is on demand and no part of `devops ci`.
- **Write the spec text through the spec delta of this change and not by editing `openspec/specs/`.**: Only the archive of a change writes the living specs, so a direct edit would break the grounding of the pull request.

## Rejected alternatives

- **Keep the command in `src/devops_cli/commands/roadmap.py` and add an alias under the eval group.**: `README.md` states the pre-1.0 policy of no legacy references, shims or compatibility remnants, and the issue names two places for evaluations as the problem.
- **Expose the moved command as an MCP tool instead of excluding it.**: `tests/ai/mcp/test_mcp.py` excludes every command of the eval group, and the command calls a model and writes nothing.
- **Rewrite the changelog line and the archived change that hold the old name.**: `CONTEXT.md` makes the changelog line the record of a release and an archived change the record of a past delivery.
- **Wait for #3182 before this change.**: `tests/ai/mcp/test_mcp.py` already holds `("roadmap", "eval", "verify"),`, so that pull request is merged in this tree.
