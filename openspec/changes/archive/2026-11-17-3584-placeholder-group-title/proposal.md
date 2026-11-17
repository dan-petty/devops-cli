# Proposal: #3584

## Why
The plan check and the ready mark accept a plan whose task group title is a placeholder word. A plan with no real content can reach the ready state. The check must refuse an artifact that holds a placeholder group title.

## What Changes
- Add `group_title_problems` to `src/devops_cli/roadmap/stage/stage_change.py` to check task group titles with `is_placeholder`.
- Call `group_title_problems` in `content_problems`.
- Update `Draft.change` handling in `src/devops_cli/roadmap/implement/implement_pull.py` to check `tasks.md` group titles for `DraftKind.STAGE_PLAN`.
- Update `_settle` in `src/devops_cli/roadmap/stage/stage_ready.py` to read `tasks.md` at the head commit and pass its text in `Draft.change`.

## Capabilities
- `roadmap-stage/task-groups`: Refusal of a placeholder group title in plan check and shared helper.
- `roadmap-stage/ready`: Refusal of a placeholder group title on stage plan draft and reading `tasks.md` at head commit.

## Impact
- A plan with a placeholder group title is refused by `content_problems` and `draft_readiness`.
- Short valid group titles such as `Archive` remain accepted.

## Feasibility
The plan check and ready mark currently accept a task group with title `x`.
`is_placeholder` in `pull_form.py` identifies placeholder words such as `x`, `todo`, `tbd`, and `placeholder`.

## Existing Tool Considered
No open tool parses OpenSpec task group titles and applies repository placeholder rules. This change reuses the existing `is_placeholder` helper. It requires about 50 lines of code.
