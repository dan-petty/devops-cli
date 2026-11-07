# Proposal

## Why

`devops roadmap plan-check` must report an open issue that a plan depends on, and no plan record carries such a dependency (#3224). The change folder, the stage reply and the check hold no form for an issue that must be delivered first, so a person reads a plan that waits on an open issue as ready.

## What Changes

- Add `issue_dependencies` to `src/devops_cli/roadmap/stage/stage_change.py`: it returns the issue number of each `dependencies` entry of the form `#<number>: <reason>` and skips every other entry.
- Read the `## Dependencies` section of `proposal.md` into `StageProposal.dependencies` in `src/devops_cli/roadmap/plan_read.py`.
- Report one problem with the rule `issue-dependency` in `src/devops_cli/roadmap/plan_check.py` for each issue dependency whose state is open, read through the `PlanReads` client.
- Add the problem text and the dry-run read to `src/devops_cli/lang/en/messages.py`.
- Name the issue form in the dependencies rule of `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Cover the round trip, the number reader, the open case and the case that is not open in `tests/roadmap/test_roadmap_plan_read.py`, `tests/roadmap/stage/test_roadmap_stage_form.py`, `tests/roadmap/stage/test_roadmap_stage_content.py` and `tests/roadmap/test_roadmap_plan_check.py`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-check`: The plan reader reads the dependencies of a plan, The number reader takes only the issue form, Plan-check reports an open issue dependency
- `roadmap-stage`: The planner prompt names the issue form of a dependency

## Impact

- Code: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_plan_read.py`, `tests/roadmap/stage/test_roadmap_stage_form.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probes confirm the premise of the check. They say: The path `src/devops_cli/roadmap/plan_check.py` is a file of the staging commit. The module that reports the problems is therefore there to change.
- The issue cites a path that moved. The probes say: Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it. The plan cites the module at its present path `src/devops_cli/roadmap/stage/stage_change.py`.
- The issue asks for a `dependencies` list on `StageProposal`, and the field already exists. `src/devops_cli/roadmap/stage/stage_change.py:class StageProposal` holds `dependencies` as a list of lines, so the plan adds the issue form to that list and no second field.
- The writer already writes the section. `src/devops_cli/roadmap/stage/stage_change.py:def _proposal_file` writes `## Dependencies` with one bullet for each entry and no bullet for an empty list, so the plan changes no renderer.
- The reader does not read the section back. `src/devops_cli/roadmap/plan_read.py:def read_change` passes no `dependencies` to `StageProposal`, so the list is empty for every plan that the check reads.
- `plan_check` needs a checkout of the repository for its git reads and a client of the GitHub service for `read_pull` and `get_issue`.
- `read_pull` needs a client of the GitHub service for `get_pull` and `get_issue`, and `get_issue` needs that client and a network. The check reaches both through the injected `PlanReads` client, and a test passes a fake.
- `read_change` needs no checkout, no client and no network: it takes the files of the change folder as a mapping.
- `render_change` needs no checkout, no client and no network: it takes the proposal and returns the files of the change folder as a mapping.
- The first checks against the real system: `uv run devops roadmap plan-check <pull-request>` reads the change folder at the head of a real plan pull request and reports each open issue dependency, and `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` runs the offline cases with a fake client.

## Existing Tool Considered

Fission-AI/OpenSpec (MIT, maintained, last activity 2026-11-05) gives the change folder, its `proposal.md` and a validator, so the `## Dependencies` section has a home. It holds no field of the stage reply, no reader that returns the issue numbers of the section, and no read of GitHub issue state. The change builds that code in `src/devops_cli/roadmap/`. To build it costs about 45k tokens to write, about 6k tokens a month to keep and fix, and about 3 hours of elapsed time. The change deletes no internal code.

## Dependencies

- Pull request #3955 changes `src/devops_cli/commands/roadmap.py`.
