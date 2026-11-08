# Proposal

## Why

#3212: The stage check accepts a spec delta on a plan that changes only root documents or knowledge-base manuals. The golden set replay then records a defect that the path rule misses. The rule must treat root documents outside `src/` and paths under `src/devops_cli/ai/knowledge_base/` as paths that need no spec delta.

## What Changes

- Add `src/devops_cli/ai/knowledge_base/` to `_NO_SPEC_PREFIXES` in `src/devops_cli/roadmap/stage/stage_change.py`.
- Add helper `_is_no_spec_path` to treat markdown files outside `src/` as paths that need no spec delta.
- Update `_needs_no_spec` in `src/devops_cli/roadmap/stage/stage_change.py` to use `_is_no_spec_path`.
- Update line 18 of `src/devops_cli/ai/tasks/roadmap_stage_change.md` to name the knowledge-base prefix.
- Update `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` to use an observable source path instead of `README.md`, and test root documents and knowledge-base manuals.
- Update case `2526` in `tests/fixtures/roadmap_eval/stage/2526-the-five-defect-fixes-merged-on/case.json` to assign gate `paths` and remove its reason.
- Add test coverage in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` for case `2526`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Refuse a spec delta that the changed paths do not need

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`
- Fixtures: `tests/fixtures/roadmap_eval/stage/2526-the-five-defect-fixes-merged-on/case.json`

## Feasibility

- The premise was confirmed in `src/devops_cli/roadmap/stage/stage_change.py`. `_NO_SPEC_PREFIXES` lists only `tests/`, `.github/workflows/`, `docs/` and `openspec/`.
- The probe confirms that `src/devops_cli/roadmap/stage/stage_change.py` is a file of the repository.
- The probe confirms that `tests/fixtures/roadmap_eval/stage/2526-the-five-defect-fixes-merged-on/case.json` has an unjudged defect for `spec_delta_wrong`.
- The first check of the implementation is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.
- The second check of the implementation is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

## Existing Tool Considered

No open, maintained tool covers this project-specific rule. The change extends project code. The cost to build is 4,000 tokens and 30 minutes. To keep: nothing new. It deletes no code.

## Dependencies

None.
