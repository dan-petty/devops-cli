# Proposal

## Why

A plan of #3400 cites `_plan_texts` at a line that moved between the refine record and the staged commit, so a reader finds another function and the proof that the premise holds is false. The stage job accepts such a plan because `check_proposal` checks no citation, and the defect repeats in each plan that copies a line from its refine block. #3422 adds the check and a symbol citation that survives a move.

## What Changes

- `check_proposal` in `src/devops_cli/roadmap/stage_change.py` resolves each `path:line:text` citation of `feasibility`, `why` and `what_changes` against the staged file and refuses one whose line does not hold the text, or whose path or line is absent.
- `check_proposal` resolves a `path:def name` or `path:class name` citation against the staged file and refuses one whose symbol the file does not define.
- `check_proposal` takes an optional `read_text` callable, and it judges no citation when it holds none, so the replay of the golden set stays unchanged.
- The cited text and the staged line are compared after white space is collapsed in both, and a citation of fewer than 3 characters is refused.
- `src/devops_cli/roadmap/stage.py` passes a `read_text` callable to `check_proposal` that reads a cited file at the staged commit with the `git show <sha>:<path>` form, so the check reads the staged commit and not the working tree; the replay of the golden set passes no reader.
- The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` asks the planner to cite a symbol instead of a line number when a line is not needed.
- `tests/roadmap/test_roadmap_stage_content.py` and `tests/roadmap/test_roadmap_stage_prompt_rules.py` hold the new rules, so the change carries a spec delta on the stage job.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Refuse a stale line citation, Accept a true line citation, Refuse a citation of an absent line, Resolve a symbol citation, Refuse an absent symbol, Scan the three evidence fields, Judge no citation without file text, Compare a citation with collapsed white space, The stage job reads the text of a cited file at the staged commit, The stage prompt prefers a symbol citation

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_content.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probe confirms the premise at the staged commit by symbol, the form that survives a move: `src/devops_cli/roadmap/stage_change.py:def _plan_texts` defines `_plan_texts(proposal: StageProposal) -> list[tuple[str, str]]`.
- The refine block of the issue copied the line number of `_plan_texts` from a commit that is not the staged one, which is the defect the issue reports; the check must read the staged file and not a copied number.
- `read_file` on `src/devops_cli/roadmap/stage_paths.py` shows `class StagedTree` holds the tracked files of a checkout as a list (`read` runs `git ls-files` and returns that list, and the class keeps no checkout and no file text) and has no method that returns the text of a file, so the reader of a cited file must come from the checkout the stage job holds, not from the tree.
- `read_file` on `src/devops_cli/roadmap/stage.py` shows `_Planner` holds `source` (the checkout) and `sha` (the staged commit) and calls `check_proposal`, so it can read a cited file at the staged commit with the `git show <sha>:<path>` form that `src/devops_cli/roadmap/planned.py` and `src/devops_cli/roadmap/refine.py` already use, and pass that reader to `check_proposal`.
- `read_file` on `src/devops_cli/roadmap/stage_eval_gates.py` shows the replay calls `check_proposal` with no reader, so it judges no citation and its recorded plans keep passing.
- `read_file` on `tests/roadmap/test_roadmap_stage_content.py` shows `_check` passing a `StagedTree` built from a list of paths, so a test doubles the file text with a dict lookup as `read_text` and reaches no disk and no network.
- First check against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` on the new tests.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` on the prompt rule.
- Third check: `uv run devops roadmap eval stage --replay` on the whole golden set, which must catch the same defects and refuse no good plan.
- Fourth check: `uv run devops roadmap eval stage --model <model>` before and after the change, because the rule of `docs/ROADMAP_WORKFLOW.md` asks a change of `check_proposal` or of the stage prompt to state the score of one model before and after.

## Existing Tool Considered

No open, maintained tool covers a repository-specific proof rule that resolves a citation against one staged commit, so the change builds its own code: about 4k tokens to implement, about 1k tokens per year to keep and fix it, and about 4 hours of elapsed time. It extends the existing `check_proposal` text scan and the `git show` read of a file at a commit, adopts no new dependency and deletes no internal code.

## Dependencies

None.
