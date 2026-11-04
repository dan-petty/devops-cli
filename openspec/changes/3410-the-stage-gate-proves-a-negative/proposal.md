# Proposal

## Why

The stage gate checks the form and the paths of a verify command, but never whether a negative search can pass on the tree that the plan produces. #3378 planned a move of the stage modules and gave a whole-prefix negative search, and #3410 makes the gate record the staged hits and refuse a search that proves nothing or that a created module keeps.

## What Changes

- Add the parser of a negative-search command, the recorder of its staged hits and the search gate to src/devops_cli/roadmap/stage_form.py.
- Take the recorded evidence as a keyword of check_proposal in src/devops_cli/roadmap/stage_change.py and refuse the two faults.
- Record the evidence in src/devops_cli/roadmap/stage.py before the reply is judged, and again for the groups of a split.
- Read the evidence from the eval case in src/devops_cli/roadmap/stage_eval_gates.py, with no git call.
- Add the case of the plan of #3378 with the two refusals and the accepted literal.
- Ask the planner in src/devops_cli/ai/tasks/roadmap_stage_change.md to search the literal and to quote the hit count in feasibility.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The stage job records the hits of a negative search, A negative search with no staged hit is refused, A negative search that a created module keeps is refused, A negative search with a surviving hit is accepted, The stage prompt asks for the hit count of a negative search
- `roadmap-stage-eval`: The replay reads the search evidence from its case, The golden set holds the case of a kept negative search

## Impact

- Code: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_gates.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_form.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_negative_search.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- `probes` confirms each cited file of the target subsystem, word for word: "The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit."
- "The path `src/devops_cli/roadmap/stage.py` is a file of the staging commit."
- "The path `src/devops_cli/roadmap/stage_form.py` is a file of the staging commit."
- "The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit."
- "The path `devops_cli.roadmap.stage_` is no file of the staging commit." The literal names no path, so a search for it matches the import lines and the paths of the moved package, which is the fault of #3378.
- The code of `check_proposal` in the context calls form_problems, path_problems, move_prefix_problems and move_verify_problems, and no check of the hits of a negative search, so the premise holds.
- The first check the implementation runs against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py`.
- Then `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` and `uv run devops ci test tests/roadmap/test_roadmap_stage_negative_search.py`.

## Existing Tool Considered

The existing git grep, search_code and references stage tools cover the search need: about 10k tokens and 1 hour to build the gate, and nothing to keep.

## Dependencies

None.
