# Proposal: #3465

## Why

The plan of PR #3439 proved its premise with another open change's proposal. Its `## Feasibility` cited `openspec/changes/3307-the-plan-check-names-a-caller/proposal.md`, a plan that holds no commit but `docs(openspec)`, and claimed a `StagedTree.callers` method that `src/devops_cli/roadmap/stage/stage_paths.py` does not define. The gates accepted the plan and the service opened it as a draft. The prompt lets a plan prove a premise with any text, so a plan can cite another plan's proposal and pass. Closes #3465.

## What Changes

- The stage prompt states that a `feasibility` line proves its claim with the source at the staged commit, and never with the `proposal.md` or `design.md` of a change that is not in `openspec/changes/archive/`.
- `check_proposal` refuses a `feasibility` line that cites `openspec/changes/<other>/proposal.md` or `design.md` for a change that is not archived. The problem names the path and the gate is `citation`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/trace-gate`: An open change's plan is no feasibility evidence.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Prompt: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

Read on 2026-11-14 against `origin/main` at `04107728d`.

- The false claim of #3439: `class StagedTree` at `src/devops_cli/roadmap/stage/stage_paths.py` holds a tuple of tracked files, and no `callers` method exists; `git log --oneline -- openspec/changes/3307-the-plan-check-names-a-caller` holds only a plan commit.
- The evidence gate: `src/devops_cli/roadmap/stage/stage_change.py:2413:ProposalGate.CITATION` runs the citation rules over `_evidence_texts(proposal)`.
- The prompt rule sits with the other Feasibility rules: `src/devops_cli/ai/tasks/roadmap_stage_change.md:10`.
- The new rule and its tests run on the branch: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py`.

## Existing Tool Considered

No open, maintained tool judges whether a plan cites a plan as evidence. The rule extends `_plan_citation_problems`, which already reads each evidence field of the plan, and adopts no new dependency. The cost is about 30 lines of code, 60 lines of tests, and under an hour.
