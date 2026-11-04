# Proposal

## Why

A plan of #3400 cites `_plan_texts` at a line that moved between the refine record and the staged commit, so a reader finds another function and the proof that the premise holds is false. The stage job accepts such a plan because `check_proposal` checks no citation, and the defect repeats in each plan that copies a line from its refine block. #3422 adds the check and a symbol citation that survives a move.

## What Changes

- `check_proposal` in `src/devops_cli/roadmap/stage_change.py` resolves each `path:line:text` citation of `feasibility`, `why` and `what_changes` against the staged file and refuses one whose line does not hold the text, or whose path or line is absent.
- `check_proposal` resolves a `path:def name` or `path:class name` citation against the staged file and refuses one whose symbol the file does not define.
- `check_proposal` takes an optional `read_text` callable, and it judges no citation when it holds none, so the replay of the golden set stays unchanged.
- The cited text and the staged line are compared after white space is collapsed in both, and a citation of fewer than 3 characters is refused.
- `StagedTree` in `src/devops_cli/roadmap/stage_paths.py` reads the text of one tracked file of its checkout, and `src/devops_cli/roadmap/stage.py` passes that reader to `check_proposal`, so the check reads the staged commit and not the working tree.
- The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` asks the planner to cite a symbol instead of a line number when a line is not needed.
- `tests/roadmap/test_roadmap_stage_content.py`, `tests/roadmap/test_roadmap_stage_paths.py` and `tests/roadmap/test_roadmap_stage_prompt_rules.py` hold the new rules, so the change carries a spec delta on the stage job.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Refuse a stale line citation, Accept a true line citation, Refuse a citation of an absent line, Resolve a symbol citation, Refuse an absent symbol, Scan the three evidence fields, Judge no citation without file text, Compare a citation with collapsed white space, The staged tree reads the text of a cited file, The stage prompt prefers a symbol citation

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_content.py`, `tests/roadmap/test_roadmap_stage_paths.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probe confirms the premise at the staging commit: `_plan_texts` is defined at src/devops_cli/roadmap/stage_change.py:556:def _plan_texts(proposal: StageProposal) -> list[tuple[str, str]]:
- The issue's own line 551 for `_plan_texts` is the number that the refine record read at another commit, which is the defect that the issue reports; the check must read the staged file and not a copied number.
- `read_file` on `src/devops_cli/roadmap/stage_paths.py` shows `class StagedTree` with `read`, which lists the tracked files with `git ls-files` and keeps the checkout, and with a `callers` method that reads that checkout with `git grep`; the change folder `openspec/changes/3307-the-plan-check-names-a-caller/proposal.md` states it: "`StagedTree.read` keeps the checkout, and `StagedTree.callers` returns the files of the commit that call a function, found with `git grep`. A tree built from a list of files, as the replay builds it, has no checkout and skips the check."
- `read_file` on `src/devops_cli/roadmap/stage_paths.py` shows no method that returns the text of one file, so the change adds that method to the class that holds the checkout, and it judges nothing when the tree has no checkout.
- `read_file` on `src/devops_cli/roadmap/stage.py` shows the stage job builds the tree with `StagedTree.read(checkout, ...)`, so the checkout is at hand where it calls `check_proposal`.
- `read_file` on `tests/roadmap/test_roadmap_stage_content.py` shows `_check` passing a `StagedTree` built from a list of paths, so a test doubles the file text with a dict lookup and reaches no disk and no network.
- First check against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` on the new tests.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` on the reader of the staged text.
- Third check: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` on the prompt rule.
- Fourth check: `uv run devops roadmap eval stage --replay` on the whole golden set, which must catch the same defects and refuse no good plan.
- Fifth check: `uv run devops roadmap eval stage --model <model>` before and after the change, because the rule of `docs/ROADMAP_WORKFLOW.md` asks a change of `check_proposal` or of the stage prompt to state the score of one model before and after.

## Existing Tool Considered

No open, maintained tool covers a repository-specific proof rule that resolves a citation against one staged commit, so the change builds its own code: about 4k tokens to implement, about 1k tokens per year to keep and fix it, and about 4 hours of elapsed time. It extends the existing `check_proposal` text scan and the `StagedTree` reader of the checkout, adopts no new dependency and deletes no internal code.

## Dependencies

None.
