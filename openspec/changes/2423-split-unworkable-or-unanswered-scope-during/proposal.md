# Proposal

## Why

Issue #2423 reports that when `devops roadmap refine` finds unworkable parts or unresolved questions in an issue, it blocks the whole item or sends it to a person. Workable subsets remain delayed behind the blocked parts. The change lets refine remove unworkable scope into new issues so the workable scope can proceed.

## What Changes

- The refine prompt gains instructions to identify unworkable scope and propose it as separate issues in a split_issues field.
- The refine orchestrator reads split_issues from the model response and creates a new issue for each entry via the existing intake path.
- The orchestrator records a link between the original issue and each newly created issue.
- The remaining workable scope of the original issue proceeds toward Ready status.
- Tests cover the scope-splitting behavior end to end.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: scope-splitting-on-unworkable-parts, split-issue-creation-via-intake, split-issue-linking

## Impact

- Code: `src/devops_cli/roadmap/refine.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`
- Tests: `tests/test_roadmap_refine_split.py`

## Feasibility

- The refine prompt file `src/devops_cli/ai/tasks/roadmap_refine_proposal.md` is present in the context and shows the current instructions. It has no scope-splitting instructions, confirming the gap described in #2423.
- The `roadmap-refine` capability exists in the spec list, so new requirements are added to it.
- CONTEXT.md confirms that intake is the single entry point for turning a candidate into an item, and that a candidate is never a duplicate of the issue it is split from. This validates the design of reusing intake for split-off issues.
- The exact orchestrator file path is not shown in the context. The implementation step must confirm it by searching for the refine command handler, likely under `src/devops_cli/roadmap/`. First check: `grep -r 'roadmap refine' src/devops_cli/ --include='*.py' -l`.
- First check the prompt file for the absence of split instructions: `grep -c 'split_issues' src/devops_cli/ai/tasks/roadmap_refine_proposal.md` should return 0.
- First check that the intake path is callable from the orchestrator: `grep -r 'def intake' src/devops_cli/roadmap/ --include='*.py'`.

## Existing Tool Considered

The devops-cli's own `roadmap intake` command and roadmap store handle issue creation and board updates. The change extends the existing refine prompt and orchestrator. No new external dependency is added. The written cost is the prompt edit, the orchestrator branch for split_issues, and the link-recording call, all within the existing codebase.
