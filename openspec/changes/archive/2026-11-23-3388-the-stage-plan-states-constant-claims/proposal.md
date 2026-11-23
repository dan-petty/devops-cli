# Proposal

## Why

The plan check reads constant claims from prose, so it skips a sentence with two numbers and a new name for an existing bound, and a wrong bound passes (#3388).

## What Changes

- Add `StageConstantClaim` with `name` and `value`, and the `constant_claims` list with an empty default, to `StageProposal` in `src/devops_cli/roadmap/stage/stage_change.py`.
- Refuse a claim whose value differs from the staged value, and a claim whose name the staged values do not hold, in `check_proposal`.
- Run the prose scan of constant claims only when `constant_claims` is empty.
- Add `stage_problem_constant_undefined` to `src/devops_cli/lang/en/messages.py` for a claim that names no module-level integer of the staged tree.
- List `constant_claims` among the reply keys of `src/devops_cli/ai/tasks/roadmap_stage_change.md`, with the rule that a claim names a constant of the staged tree and that a constant the plan creates is no claim.
- Add `claimed_names` to `src/devops_cli/roadmap/stage/stage_constants.py` and call it in `src/devops_cli/roadmap/stage/stage.py`, so the reader sees each claimed name.
- Describe the claim list in `docs/roadmap/stage.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/claims`: The stage reply holds structured constant claims, A structured claim matches the staged value, The prose scan runs only when the claim list is empty, A caller with no staged values judges no claim, The stage job reads the value of each claimed name, The prose scan ignores a constant that the staged tree does not define, The prompt asks for the staged value of a constant

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_constants.py`, `src/devops_cli/roadmap/stage/stage.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/roadmap/stage.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_constants.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`

## Feasibility

- The earlier plan of this item said the base held no staged-constant reader. The base has moved, and this plan builds on that reader instead of creating it: `search_code` for `staged_constants` returned `src/devops_cli/roadmap/stage/stage_constants.py:229:def staged_constants(source: Path, sha: str, names: Iterable[str]) -> dict[str, int]:` and `src/devops_cli/roadmap/stage/stage.py:2230:constants = staged_constants(self._source, self._sha, candidate_names(plan_texts(proposal)))`.
- The issue cites paths of an older commit, and the probes say: "The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_change.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it." The plan uses the staged paths.
- The probes say of the test paths: "The path `tests/roadmap/test_roadmap_stage_constants.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_constants.py`. No commit in the history deleted or renamed it." `list_files` of `tests/roadmap/stage` showed `test_roadmap_stage_constants.py`, `test_roadmap_stage_plan.py`, `test_roadmap_stage_prompt_rules.py` and `test_roadmap_stage_apply.py`, so the plan changes those modules and creates none.
- `search_code` for `constant_problems` returned `src/devops_cli/roadmap/stage/stage_change.py:2440:ProposalGate.CONSTANTS: constant_problems(plan_texts(proposal), constants or {}),`, the prose scan that the plan keeps as the fallback.
- `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` lines 2445 to 2467 showed `def check_proposal(` with `src/devops_cli/roadmap/stage/stage_change.py:2460:constants: Mapping[str, int] | None = None,`, so the staged values already reach the check as a keyword-only mapping.
- `read_file` of the same file lines 673 to 716 showed `class StageProposal(_Reply):` with `src/devops_cli/roadmap/stage/stage_change.py:699:security: Line = ""` as its last field, and no `constant_claims` field.
- `read_spec` of `roadmap-stage/claims` returned the requirement `A constant that the staged tree does not define is ignored` with its three scenarios, so the plan renames that requirement and keeps all three.
- `search_code` for `cite the staged` returned `src/devops_cli/ai/tasks/roadmap_stage_change.md:11:give no new name to the bound of a constant that the staged tree defines`, the prompt rule that the new key bullet sits beside.
- The plan relies on `SUMMARY_MAX_CHARS`, whose staged value is 60: `src/devops_cli/roadmap/pull_form.py:40:SUMMARY_MAX_CHARS: Final[int] = 60`.
- The plan uses no claim of `BODY_MAX_CHARS`, because the staged tree defines it twice with different values and so gives it no one value: `src/devops_cli/roadmap/stage/stage_change.py:125:BODY_MAX_CHARS: Final[int] = 800` and `src/devops_cli/roadmap/pull_form.py:55:BODY_MAX_CHARS: Final[int] = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS`.
- `staged_constants` needs a checkout of the repository at the staged commit, because it runs `git grep` and `git show` (`src/devops_cli/roadmap/stage/stage_constants.py:229:def staged_constants(source: Path, sha: str, names: Iterable[str]) -> dict[str, int]:`).
- `claimed_names` needs no checkout, no client and no network: it reads the plan texts and the claimed names that the reply gives.
- `constant_problems` needs no checkout, no client and no network: the caller gives the staged values as a mapping (`src/devops_cli/roadmap/stage/stage_constants.py:257:def constant_problems(texts: Iterable[str], constants: Mapping[str, int]) -> list[str]:`).
- `check_proposal` needs no checkout, no client and no network: it takes the staged values as an argument, and the replay passes the recorded ones (`src/devops_cli/roadmap/stage/stage_eval_gates.py:145:constants=dict(case.facts.constants),`).
- The first check against the real system is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_constants.py`, which fails on the base because `StageProposal` holds no `constant_claims` field and no `StageConstantClaim` model.
- The second is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, which fails on the base because the reply keys of the prompt and the schema of `StageProposal` hold no `constant_claims`.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_plan.py` lines 2751 to 2801 showed `tests/roadmap/stage/test_roadmap_stage_plan.py:2751:def test_check_proposal_refuses_a_plan_number_differing_from_a_constant() -> None:` with the prose case that the plan keeps as the fallback.
- `search_code` for `stage_problem_constant_mismatch` returned `src/devops_cli/lang/en/messages.py:4910:stage_problem_constant_mismatch: str = (` and `src/devops_cli/roadmap/stage/stage_constants.py:278:texts_msg.stage_problem_constant_mismatch.format(`, so the mismatch message exists and the plan adds one message for a claim the staged values do not hold.
- `search_code` for `candidate_names` returned `src/devops_cli/roadmap/stage/stage_constants.py:288: "candidate_names",` and `src/devops_cli/roadmap/stage/stage_constants.py:287:__all__ = [`, so the new `claimed_names` joins that export list.
- The verifies run `uv run devops ci test`, `uv run devops ci docs` and `uv run devops roadmap eval stage --replay`. Each program is `devops` of the runner image, and the pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL` apply.
- No verify needs a network, a cluster token or a scanner, so no failure class of the runner image is needed and no program is `NOT_IN_RUNNER`.
- The behavior of the model on the changed prompt is not checked by this run: the replay score before and after the change is a task of groups 1 and 2.

## Existing Tool Considered

No open, maintained tool compares the constant claims of a plan with the module-level integers of a staged tree. The change reuses `ast`, `git grep` and `git show` through `staged_constants` and adds no dependency. Cost: 12k tokens to build, 3k tokens a month to keep and fix, and 1 to 2 days.

## Dependencies

None.
