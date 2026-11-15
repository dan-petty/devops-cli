# Proposal

## Why

A stage plan of #3368 said that the implement job writes the delivery title with no check, while the helper that both call sites call already ran that check. The plan read the two call sites and not the body of the helper, so it duplicated a guard that the base holds and added a requirement that the base spec already states. For #3416, the premise probe must find a claimed missing check in the helpers of a cited call site and in the base tree, and the stage job must return the item with that evidence instead of planning a duplicate.

## What Changes

- Add `claimed_missing_checks` and `check_claims` to `src/devops_cli/roadmap/stage/stage_probe.py`: the scan of the plan texts for a claim that a call site runs no named check, and the read-only search of the call site's body, the helpers that it calls in its file, and the source files of the staging commit.
- Add the `left` field to `Probe` and the probe message that names the path and the line of a check that a plan says is missing, in `src/devops_cli/lang/en/messages.py`.
- Return the item to New from `src/devops_cli/roadmap/stage/stage.py` when the search finds the check, with a `PremiseKind.MISSING_CHECK` kind on `FalsePremise`, a comment that names the path and the line, and `refine.next_step` `retry`.
- Add the probe tests to `tests/roadmap/stage/test_roadmap_stage_probe.py` and the plan-level tests to `tests/roadmap/stage/test_roadmap_stage_plan.py`.
- Add two requirements to `openspec/specs/roadmap-stage/premise/spec.md` and change the return requirement of `openspec/specs/roadmap-stage/returns/spec.md` through the spec delta of the change.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/premise`: The job probes a claimed missing check in a helper of its call site, The job searches the base tree for a claimed missing check
- `roadmap-stage/returns`: A false absence or a claimed missing check returns the item

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_probe.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`

## Feasibility

- The premise of the issue holds, and the path that it cites moved. `probes` says: "The path `src/devops_cli/roadmap/implement_run.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_run.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it."
- `read_file` of the staged file shows the check in the helper: `src/devops_cli/roadmap/implement/implement_run.py:1463:def _delivery_title(self) -> str:`, then `src/devops_cli/roadmap/implement/implement_run.py:1475:if not title_problems(title, declared):` and `src/devops_cli/roadmap/implement/implement_run.py:1480:raise _StopError(`. The issue cites line 957 of the old path, so its line number is stale.
- `search_code` for `_delivery_title(` shows the two call sites of the helper: `src/devops_cli/roadmap/implement/implement_run.py:1434:title = self._delivery_title()` and `src/devops_cli/roadmap/implement/implement_run.py:1551:delivery_title = self._delivery_title()`. A plan that reads only those two lines misses the body of the helper, which is the defect of #3368.
- The base spec that the issue cites moved too: `probes` says "Commit dfb09bd1 2026-11-12 refactor(openspec): split big capabilities into nested ones (#4981) deleted or renamed it." The plan adds no requirement about the delivery title, so it duplicates no base requirement. The text of the nested capability `roadmap-implement-job/pull-request` is not checked by this run.
- The plan uses the staged paths that `probes` names: "The path `src/devops_cli/roadmap/stage_probe.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_probe.py`", "The path `src/devops_cli/roadmap/stage.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/ai/spend/stage.py`, `src/devops_cli/roadmap/stage/stage.py`", and "The path `tests/roadmap/test_roadmap_stage_plan.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_plan.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it."
- The probe and the settle step exist at the staged commit: `src/devops_cli/roadmap/stage/stage_probe.py:341:def probe_premise(source: Path, sha: str, body: str) -> Probe:` returns the lines that the model reads, and `src/devops_cli/roadmap/stage/stage.py:2121:-> StagedChange | OverBudget | _Refused:` is the return of the settle step that every reply reaches. `src/devops_cli/roadmap/stage/stage_probe.py:class Probe` and `src/devops_cli/roadmap/stage/stage_probe.py:class _Run` already hold the false premises and the commands left.
- The bound is staged as `src/devops_cli/config/constants.py:3454:CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS: Final[int] = 10`, and `src/devops_cli/roadmap/stage/stage_probe.py:125:left: int = CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` applies it. The claim search spends the commands that the probe of the item has left, so the item runs at most 10 commands and the plan changes no base requirement about the bound.
- The claim search reads a file of the commit with `git cat-file -p <sha>:<path>`, which is one of the three commands that `The probes are bounded and read-only` names, so the plan leaves that base requirement as it is.
- Precondition of the call `definition_lines(source, sha, name, git, commands=...)`: a checkout of the repository, because `src/devops_cli/roadmap/premise.py:94:def definition_lines(` runs `git grep` at the staging commit; it needs no client and no network.
- Precondition of the call `check_claims(source, sha, claims, left)`: a checkout of the repository, because each of its commands is a read-only git command at the staging commit; it needs no client and no network.
- Precondition of the call `claimed_missing_checks(texts)`: none, because it reads the plan texts of the reply and nothing else.
- The return that the plan reuses exists: `src/devops_cli/roadmap/stage/stage.py:925:class FalsePremise:` is an outcome of `plan()`, and `src/devops_cli/roadmap/stage/stage.py:3568:def _return_premise(store: RoadmapStore, premise: FalsePremise) -> None:` writes the comment and the Status New. `src/devops_cli/lang/en/messages.py:4016:stage_returned_premise: str = (` and `src/devops_cli/lang/en/messages.py:4021:stage_returned_premise_line: str = (` are the messages that the new kind picks apart.
- The plan answers the findings of the check: the two new premise requirements hold 438 and 365 characters, both under 500, and the plan no longer modifies `The probes are bounded and read-only`, so the base scenario that names `shared_helper` stays out of the delta and needs no new test.
- The first checks of the implementation against the real system are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py`, `uv run devops openspec check` and `uv run devops ci docs`.
- The verify programs need no new runner capability: `uv`, `python`, `devops` and `pytest` are image tools, the pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`, and a failing check is the failure class `test`.
- The plan-level test writes the sample file into the clone with `advance_origin`, which `tests/roadmap/stage/test_roadmap_stage_plan.py:247` already calls, so the tests reach no network, no cluster and no scanner.
- This run did not read #3368, #3374 or #3319 on GitHub, so the plan makes no claim about their state: not checked.

## Existing Tool Considered

No open, maintained tool checks a code premise across a call chain, and the issue's alternatives check found none. The premise probe is the repository's own tool, and this change extends it: about 8k tokens to build and test, about 1.5k tokens to keep and fix, and about 3 hours elapsed. The change deletes no internal code.

## Dependencies

None.
