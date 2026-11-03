# Proposal

## Why

The stage of #3265 passes a task group that the implement Job later stops on its size, because the two paths count tokens differently and the stage ignores the files that a group creates. One measure in both paths lets a person size the plan before the Job runs it.

## What Changes

- `src/devops_cli/ai/context_budget.py` fails with a clear error when the tiktoken cache is missing instead of counting characters, so the stage and the Job share one count.
- The stage measure in `src/devops_cli/roadmap/stage_change.py` adds the estimated lines of each created file at a fixed tokens-per-line rate.
- The stage refuses a task group whose `creates` path has no line estimate.
- The staging tasks `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md` state the 40,000-token budget and the line-estimate rule.
- Tests in `tests/ai/test_context_budget.py`, `tests/roadmap/test_roadmap_stage_plan.py`, and `tests/roadmap/test_roadmap_stage_prompt_rules.py` cover the missing cache, the shared count, the 1,500-line group, and the updated prompt rules.
- This change alters observable behavior of the stage and the Job, so it carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The group measure and the Job use one token counter, A created file counts its estimated lines, The staging prompt states the budget and the estimate rule

## Impact

- Code: `src/devops_cli/ai/context_budget.py`, `src/devops_cli/roadmap/stage_change.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`
- Tests: `tests/ai/test_context_budget.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- `probes`: "The path `src/devops_cli/ai/context_budget.py` is a file of the staging commit."
- `probes`: "The path `tests/roadmap/test_roadmap_stage_plan.py` is a file of the staging commit."
- `probes`: "`creates` is defined at src/devops_cli/roadmap/stage_change.py:260: creates: list[RepositoryPath] = Field(default_factory=list)"
- `read_file` of `src/devops_cli/ai/context_budget.py` shows `count_tokens` returning `max(1, math.ceil(len(text) / 4))` when `_get_tiktoken_encoding` gives `None`, which confirms defect 1 of the issue.
- `read_file` of `src/devops_cli/roadmap/stage_change.py` shows the group measure adding the tokens of the named existing paths only, which confirms defect 2.
- First check: `uv run devops ci test tests/ai/test_context_budget.py`, which shows whether a missing cache still counts characters.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, which shows how the stage measures a group that creates a large file.

## Existing Tool Considered

`tiktoken` is the open, maintained BPE token counter that the repository already uses, and this change keeps it as the one counter in the stage and the Job. It ships no bundled offline encoding cache, so the change fails clearly when the cache is missing rather than building a second counter. Building and keeping a custom counter would cost about 15,000 tokens of code and tests, and about 30,000 tokens a year to fix its drift from the real encoding, over roughly two days of elapsed work. No internal code is deleted.
