# Proposal

## Why

The stage context gives the planner the names of a capability's requirements only, and the duplicate check compares names only (#3246). A plan then adds a requirement whose name is new while a base requirement of the same spec states, or contradicts, the behavior: #3225, #3228 and #3234 each needed a modified block that the planner did not write, and the first plans of #3150, #3151 and #3158 had the same fault.

## What Changes

- Add `requirement_text`, `REQUIREMENT_TEXT_MAX_COUNT` (12) and `REQUIREMENT_TEXT_MAX_CHARS` (6000) to `src/devops_cli/roadmap/stage/stage_specs.py`, with a name match before a text match and the count cut before the character cut.
- Append a `### Requirement text` section to the plan request context in `_Planner._request` of `src/devops_cli/roadmap/stage/stage.py`, and add nothing when no requirement matches.
- Add a `requirements` field to `VerificationInput` of `src/devops_cli/roadmap/stage/stage_verify.py`, fill it in `of` from the base specs of the checkout, write it in `payload` and yield it in `request_texts`.
- Pass the base specs to that field from `_Planner._input_of` of `src/devops_cli/roadmap/stage/stage.py` and from `_run_cases` of `src/devops_cli/roadmap/stage/stage_verify_eval.py`, so the review and its replay read the same text.
- Add the golden-set case `tests/fixtures/roadmap_eval/stage/3225-a-plan-adds-a-requirement-that/case.json` from the review of #3225 with every key that `StageCase` requires, register pull 3225 in `EVALUATED_PULLS`, and replay the case through the review.
- Tell the planner in `src/devops_cli/ai/tasks/roadmap_stage_change.md` to use modified when a requirement of the context states the behavior, name `requirements` in `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, and document the section and its two bounds in `docs/roadmap/stage.md`.
- The change carries a spec delta: the plan request, the review request and the prompts are behavior that a consumer of the stage job observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/context`: The stage context holds the text of a cited requirement, The stage context bounds the requirement text, The stage context orders the requirement text by relevance
- `roadmap-stage/spec-delta`: The stage prompt names modified for a stated behavior, The model input holds the purpose and the requirement names of each capability
- `roadmap-stage/verification`: A quote of the requirement text opens a finding, The first review of a plan sends the bounded requirement text

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_specs.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_verify_eval.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `docs/roadmap/stage.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_specs.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verification.py`, `tests/fixtures/roadmap_eval/stage/3225-a-plan-adds-a-requirement-that/case.json`, `tests/fixtures/roadmap_eval/stage/3225-a-plan-adds-a-requirement-that/plan.json`, `tests/fixtures/roadmap_eval/stage/3225-a-plan-adds-a-requirement-that/issue.txt`, `tests/fixtures/roadmap_eval/stage/3225-a-plan-adds-a-requirement-that/facts.json`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probe confirms the module that holds the selection: "The path `src/devops_cli/roadmap/stage/stage_specs.py` is a file of the staging commit."
- The probe resolves the short name of the review pass: "The path `stage_verify.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_verify.py`. No commit in the history deleted or renamed it."
- The probe confirms the document of the plan: "The path `docs/roadmap/stage.md` is a file of the staging commit."
- The probe confirms the design that this plan follows: "The path `openspec/changes/archive/2026-11-02-3037-the-stage-job-plans-with-a/design.md` is a file of the staging commit."
- The probe stopped before the identifiers of the issue: "Not probed, the bound of 10 commands is reached: `OpenSpecTool.read_json`, `stage_change.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `openspec/changes/archive/2026-11-07-3287-detect-obsolete-spec-requirements-on-command/design.md`, `stage_verify_eval.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `src/devops_cli/roadmap/stage/stage_tools.py`, `It.relevance`, `_duplicate_problems`, `read_spec`". This plan reads the identifiers it needs with its own tools and changes none of the others.
- The finding `false_premise` at group 4 is a real defect and it is fixed: `read_file` of `src/devops_cli/roadmap/stage/stage_eval_cases.py` 120 200 showed `src/devops_cli/roadmap/stage/stage_eval_cases.py:142:where: str` and `src/devops_cli/roadmap/stage/stage_eval_cases.py:143:problem: str` as required fields of `Defect`, so group 4 now writes `where`, `problem` and `reason` beside `type`, `severity`, `evidence` and `gate`, and its test asserts the `where` and the `problem`.
- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_cases.py` 120 200 also showed `src/devops_cli/roadmap/stage/stage_eval_cases.py:101:class GateName(StrEnum)`, which holds `none`, so the defect keeps the gate `none` and its `reason` says that the recorded plan passes the name check.
- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_cases.py` 186 263 showed `src/devops_cli/roadmap/stage/stage_eval_cases.py:201:summary: str` and `src/devops_cli/roadmap/stage/stage_eval_cases.py:254:"issue_body": (folder / _ISSUE_FILE).read_text(encoding="utf-8")`, so `issue.txt` holds the body only and the title goes into `case.json`.
- `read_file` of `tests/fixtures/roadmap_eval/stage/3410-the-eval-field-group-is-dropped/case.json` showed the shape of a reviewed case: `issue`, `pull`, `change`, `merge_commit`, `base_commit`, `title`, `verdict`, `scores`, `state`, `summary`, `notes` and `defects`.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` 60 125 showed `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:71:assert (frozenset(reviewed), len(cases), len(good)) == (EVALUATED_PULLS, 59, 6)` and `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:72:assert len(EVALUATED_PULLS) == 53`, so a new reviewed case raises both counts.
- `list_files` of `tests/fixtures/roadmap_eval/stage` listed 59 case folders and `split.json`, with no case of #3225, so the replay case is new.
- `read_file` of `tests/support/roadmap_stage.py` 60 100 showed `tests/support/roadmap_stage.py:def track`, which writes files, commits them and pushes, so a test puts a spec at the head of the sample repository.
- `read_file` of `src/devops_cli/roadmap/stage/stage_verify.py` 400 520 showed `src/devops_cli/roadmap/stage/stage_verify.py:class VerificationInput` with `payload`, `request_texts` and `contains`, so one field reaches the request and the quote check.
- `read_file` of `src/devops_cli/roadmap/stage/stage_verify.py` 580 640 showed `src/devops_cli/roadmap/stage/stage_verify.py:def open_findings`, which keeps a finding only when `given.contains(f.quote)`.
- `read_file` of `src/devops_cli/roadmap/stage/stage_verify_eval.py` 226 305 showed `src/devops_cli/roadmap/stage/stage_verify_eval.py:283:with checkout_at(repository, case.base_commit, operation=_OPERATION) as source:`, so the replay of a case reads the base specs of its own checkout.
- `search_code` of `read_base_specs` gave `src/devops_cli/roadmap/stage/stage_specs.py:72:def read_base_specs(source: Path, tool: OpenSpecTool | None) -> dict[str, BaseSpec]:`.
- `search_code` of `self._specs` gave `src/devops_cli/roadmap/stage/stage.py:1266:self._specs = specs`, so the planner holds the base specs it needs.
- `search_code` of `### Registry places` gave `src/devops_cli/roadmap/stage/stage.py:2019:### Registry places`, the last section that the planner appends to the context.
- `search_code` of `def code_spans` gave `src/devops_cli/roadmap/step_files.py:91:def code_spans(text: str) -> tuple[str, ...]:`.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_plan.py` 500 575 showed `tests/roadmap/stage/test_roadmap_stage_plan.py:549:assert "### Registry places" in request["context"]`, the request test that group 2 extends.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_verify_eval.py` 60 180 showed `tests/roadmap/stage/test_roadmap_stage_verify_eval.py:def _case`, which copies a case of the set at the head of the sample repository, so the replay test of group 6 runs offline on that repository.
- `read_spec` of `roadmap-stage/context`, `roadmap-stage/spec-delta` and `roadmap-stage/verification` gave their requirement names, and none of the names of the added requirements is taken; it also gave the base text of `The model input holds the purpose and the requirement names of each capability` and of `The first review of a plan keeps its request`, which the modified entries replace with their two scenarios.
- Precondition of `read_base_specs`: a checkout of the repository, because it reads the spec file of each capability from it, and a client of the OpenSpec CLI, because it lists the capabilities with it.
- Precondition of `spec_names`: a client of the OpenSpec CLI, because it runs `openspec list --specs --json` through `OpenSpecTool.read_json`.
- Precondition of `VerificationInput.of`: a checkout of the repository, because it reads the cited files of the plan from `source`.
- Precondition of `read_change`: a checkout of the repository at the merge commit of pull 3225, because the case reads the change folder of issue 3060 at that commit.
- Precondition of `evaluate_cases`: a checkout of the repository at the base commit of the case, because `checkout_at` makes a worktree of it for each case.
- Precondition of `track`: a checkout of the sample repository, because it writes, commits and pushes the spec that the replay test reads.
- `requirement_text`, `code_spans` and `open_findings` need no checkout, no client and no network: they take values that their caller already holds.
- The two bounds are new module constants of `src/devops_cli/roadmap/stage/stage_specs.py` with the values of the issue, `REQUIREMENT_TEXT_MAX_COUNT` of 12 requirements and `REQUIREMENT_TEXT_MAX_CHARS` of 6000 characters, each with a one-line docstring beneath it, and the count applies first.
- The commands that the plan introduces run `pytest` from the runner image through `uv run devops ci test`; their failure class is `test` with the action `repair`, and `git`, `devops`, `python`, `uv` and `openspec` are tools of the runner image, no program of the plan is `NOT_IN_RUNNER`, and the pod keeps `readOnlyRootFilesystem` true, `runAsNonRoot` true, `allowPrivilegeEscalation` false, `capabilities.drop` ALL and `seccompProfile` RuntimeDefault.
- The `gh issue view` read of issue 3060 in group 4 needs the network from the runner image, and its failure class is `provider` with the action `retry`; the `git log --grep` read of the merge commit reads the local clone and needs no network.
- The first checks are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_specs.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py tests/roadmap/stage/test_roadmap_stage_verification.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, and then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.
- Overlap: #5622 changes `src/devops_cli/roadmap/stage/stage_tools.py`, which holds the read-spec tool that this plan keeps unchanged, and this plan changes no path of that pull request.

## Existing Tool Considered

OpenSpec (Fission-AI/OpenSpec, MIT, last activity 2026-11-05, maintained) holds each capability's requirements with their names and full text and its CLI prints them, but it selects none by a cited capability, requirement name, path, command or symbol, bounds none, and injects none into a plan request, a review request or a replay. The change builds the selection, the two bounds, the injections and the prompt text: about 300 lines of Python and tests, 10k tokens to build, keep and fix, and 3 hours of elapsed time. It deletes no code.

## Dependencies

- PR #5622 changes `src/devops_cli/roadmap/stage/stage_tools.py`, the file that holds the read-spec tool that this plan keeps unchanged; this plan changes no path of that pull request, so the two merge in either order.
