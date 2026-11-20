# Proposal: the argv check finds a missing required option

## Why

#4862: the devops-pr-ci skill tells agents to run `uv run devops pr describe <issue>`, but the command also needs `--summary`. `devops pr describe` failed 36 times from 2026-11-03 to 2026-11-11, 23 times with no `--summary`. The docs argv check of `devops docs check` and the stage plan-check use `src/devops_cli/core/command_resolver.py`. The resolver finds an unknown command, an unknown option and an extra argument, but not a missing required option or argument. Thus the skill line passed, and agents copied it and failed.

## What Changes

- Add the defect `missing_required` to `CommandReferenceDefect` and the message `argv_missing_required` to `src/devops_cli/lang/en/messages.py`.
- The resolver finds a missing required parameter with the option parser of Click, `Parameter.consume_value` and `Parameter.value_is_missing`. It does this when the strict parse fails, because a placeholder that fails conversion hides a `MissingParameter` error. A placeholder is one word: it fills the argument at its position and never an option. A command mention with no token after the command path gives no finding.
- Correct each document line that the new check finds:
  - `.agents/skills/devops-pr-ci/SKILL.md` line 26, `.claude/skills/devops-pr-ci/SKILL.md` line 26 and `.kilocode/skills/devops-pr-ci/SKILL.md` line 26: add `--summary "<summary>"`.
  - `docs/ROADMAP_WORKFLOW.md` line 283, `docs/ROUTINE_TASKS.md` line 291 and `docs/roadmap/implement.md` line 105: add the required `<args>` of `devops k8s run-job`.
  - `docs/roadmap/onboard.md` line 9: add the endpoint `repos/<repo>` and `-f has_issues=true` to `devops gh api -X PATCH`.
  - `docs/SELF_IMPROVEMENT.md` line 867: add the required `<targets>` of `devops review benchmark`.
  - `k8s/README.md` line 190: add the required `--title "<title>"` of `devops gh issue create`.
- `devops docs check` and the stage plan-check now refuse more command lines, and they show a new message. These are observable, so the change has spec deltas.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `docs-command-lines`: A command line that omits a required option is refused, A command line that omits a required argument is refused, A bare command mention is not refused, A placeholder fills an argument and not an option, A required parameter is given as Click parses it

### Modified Capabilities

- `roadmap-stage/claims`: A cited command that omits a required option is refused

## Impact

- Code: `src/devops_cli/core/command_resolver.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/core/test_docs_command_resolver.py`, `tests/roadmap/stage/test_roadmap_stage_command_citations.py`.
- Documents: the nine lines above.
- No command, option or configuration key changes.

## Feasibility

- `uv run devops pr describe 1` exits 2 with `Missing option '--summary' / '-s'.` (devops-cli 0.113.0, the issue log).
- Typer 0.28.0 (`uv.lock`) vendors Click as `typer._click`. `Parameter.handle_parse_result` calls `consume_value`, then `process_value`. `process_value` converts the value first and raises `MissingParameter` only after it, when `required` is set and `value_is_missing` is true (`typer/_click/core.py`, `Parameter.process_value`). So a placeholder that fails conversion in an earlier parameter hides the missing parameter, and a strict parse alone cannot find it.
- `OptionParser.parse_args` on a context with `resilient_parsing=True` returns the raw values and converts nothing. `_gives_action_option` in the resolver already runs it. The override of `consume_value` in Typer's `TyperOption` asks for no value when `resilient_parsing` is set. No `devops` command declares `prompt=` (`git grep -nE 'prompt=(True|")' src/devops_cli/commands` finds nothing).
- A probe of the first draft showed the defect of a token scan: `devops pr describe 1 -sx` passed, but `devops pr describe <issue> -sx` reported `--summary`, because the strict parse failed on `<issue>` first. The tests of group 1 hold both forms.

## Existing Tool Considered

pallets/click (BSD-3-Clause, maintained), vendored by Typer, is already in use, and the alternatives check of the issue records `in-use`. Its option parser, `consume_value` and `value_is_missing` decide if a required parameter has a value. The project adds only the defect kind, the message and the walk over the parameters. The first draft of this change scanned the tokens for each required option by hand, and this change deletes that code: `_is_missing_parameter`, `_is_option_given` and `_missing_required_option`.

## Dependencies

None.
