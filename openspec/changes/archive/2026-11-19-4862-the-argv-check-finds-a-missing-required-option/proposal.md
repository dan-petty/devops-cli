# Proposal: the argv check finds a missing required option

## Why
The devops-pr-ci skill instructs agents to run `uv run devops pr describe <issue>`.
The command requires the option `--summary`.
The command resolver only checks for unknown commands, unknown options, and unexpected arguments.
It does not report a missing required option or argument.
Because of this omission, documentation checks and stage plan checks accept invalid command lines.
Agents then copy these invalid command lines and encounter runtime errors.

## What Changes
- Add the `MISSING_REQUIRED` defect to `CommandReferenceDefect` in `src/devops_cli/core/command_resolver.py`.
- Map Click's `MissingParameter` exception to this defect when a command invocation contains arguments or options.
- Ensure that placeholders like `<issue>` fulfill arguments and not required options.
- Ignore bare command mentions that contain no tokens after the command path.
- Add user-facing message `argv_missing_required` in `src/devops_cli/lang/en/messages.py`.
- Correct document lines flagged by the new check:
  - `.agents/skills/devops-pr-ci/SKILL.md` line 26
  - `.claude/skills/devops-pr-ci/SKILL.md` line 26
  - `.kilocode/skills/devops-pr-ci/SKILL.md` line 26
  - `docs/ROADMAP_WORKFLOW.md` line 281
  - `docs/ROUTINE_TASKS.md` line 291
  - `docs/roadmap/implement.md` line 105
  - `docs/roadmap/onboard.md` line 9
  - `k8s/README.md` line 190

## Capabilities
- The command resolver detects missing required options and arguments in documented command lines.
- Stage plan checks reject proposals with missing required options or arguments.

## Impact
- Prevents invalid command invocations in documentation and skill guides.
- Does not change CLI public interface.

## Feasibility
- Uses existing Click exception handling and Typer command inspection.

## Existing Tool Considered
- Pallets Click `make_context` already raises `MissingParameter`. The project uses Click directly.
