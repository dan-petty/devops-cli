# Proposal

## Why

Refine graded 37 of 52 runs as a success in the 6 hours to 2026-11-18 20:30 UTC, and 15 runs failed with class `none` (#6327). The record of a form-check failure names no criterion and no part, the next round gives the model no failure, and the result line names no cause, so each try repeats the same request and the item stops at `failed`.

## What Changes

- `form_check_details` gives the failed check names and, for each failed criterion, the index and part that failed, such as `acceptance_criteria[0].then`, and the refine round writes that text in `refine.failure`.
- `_judge_findings` returns the recorded `refine.failure` beside the open findings of the review, so the next request carries the whole earlier failure once, and the refine proposal prompt says so.
- `CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS` (300) and `CONST_ROADMAP_REFINE_JUDGE_FINDINGS_MAX_CHARS` (2000) go, with the cuts in `_job_failure`, `_refusal` and `_failure_marks`, and the limit registry drops both entries.
- The failure class `form_check` joins the taxonomy with the action `retry`, and the refine result line writes `class=form_check` for a failure that holds a form check, with each failed part as `failed_1=acceptance_criteria.0.then`.
- The fault-case census in `tests/roadmap/test_roadmap_faults.py` names `form_check` as the one class that the fault suite cannot drive, because the suite runs the implement job.
- `docs/roadmap/refine.md` and `docs/ROADMAP_WORKFLOW.md` name the criterion and part of a form-check failure, the whole failure that the next request carries, and the class of the result line.
- The change has a spec delta: the refine record, the next request, the result line and the failure taxonomy are behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-failure-taxonomy`: The failure classes
- `roadmap-refine/proposal`: A form check failure names the criterion and the part, The next request carries the whole earlier failure, No character cap cuts a refine failure, A form check failure is a job failure that retries
- `roadmap-refine/writes`: A form-check failure writes its class and its parts on the result line

## Impact

- Code: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/failure.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/refine/test_roadmap_refine_job_failure.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/refine/test_roadmap_refine_job_result.py`, `tests/roadmap/test_roadmap_faults.py`

## Feasibility

- `probes` confirmed the cited paths: "The path `refine.failed_check` is no file of the staging commit. No commit in the history deleted or renamed it. The path `src/devops_cli/roadmap/refine/refine.py` is a file of the staging commit." The first is a key of the job record and no file, which `src/devops_cli/roadmap/refine/refine.py:3841:RefineRecordKey.FAILURE: failure.error,` shows for the key beside it.
- `read_file` on the refine module showed that the form check already reads each part of a criterion: `src/devops_cli/roadmap/refine/refine.py:1454:return all(part.strip() for part in criterion.model_dump().values())`, in `src/devops_cli/roadmap/refine/refine.py:def _complete`, and the checks are named by `src/devops_cli/roadmap/refine/refine.py:def form_checks`.
- The generic text of a form check is `src/devops_cli/roadmap/refine/refine.py:2970:return JobFailure(tuple(checks), texts.refine_failure_form)`, and `src/devops_cli/lang/en/messages.py:3055:refine_failure_form: str = "The reply of the model failed the form check."` holds that message. `src/devops_cli/roadmap/refine/refine.py:def _job_failure` builds it, and `src/devops_cli/roadmap/refine/refine.py:2944:checks = form_checks(proposal)` is where it reads the checks.
- The class that the round builds is `src/devops_cli/roadmap/refine/refine.py:427:class JobFailure:`, and it defines its three members at `src/devops_cli/roadmap/refine/refine.py:433:checks: tuple[JobCheck, ...]`, `src/devops_cli/roadmap/refine/refine.py:434:error: str` and `src/devops_cli/roadmap/refine/refine.py:435:findings: tuple[str, ...] = ()`.
- The two staged caps are `src/devops_cli/config/constants.py:3486:CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS: Final[int] = 300` and `src/devops_cli/config/constants.py:3490:CONST_ROADMAP_REFINE_JUDGE_FINDINGS_MAX_CHARS: Final[int] = 2000`, and the plan gives no new name to either bound.
- The three cuts are `src/devops_cli/roadmap/refine/refine.py:2973:room = CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS`, `src/devops_cli/roadmap/refine/refine.py:2985:(JobCheck.JUDGE_REFUSED,), lines[0][:CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS], lines` and `src/devops_cli/roadmap/refine/refine.py:3831:CONST_ROADMAP_REFINE_JUDGE_FINDINGS_MAX_CHARS`.
- The next request carries only the review findings today: `src/devops_cli/roadmap/refine/refine.py:def _judge_findings` reads the recorded lines, and the proposal prompt names the key as `src/devops_cli/ai/tasks/roadmap_refine_proposal.md:1:the open findings of the review that refused the last proposal for the issue, or an empty list`.
- The round passes no class for a failed job: `src/devops_cli/roadmap/refine/refine.py:4067:outcome, failure = result.next_step.value, None`, and the line writes `none` then: `src/devops_cli/roadmap/job_result.py:299:f"class={failure.value if failure else _NONE}",`.
- The result line holds names only, so a part reaches it with its brackets written as dots: `src/devops_cli/roadmap/job_result.py:304:fields += [f"{_name(key)}={_name(value)}" for key, value in (names or {}).items()]`, and `src/devops_cli/roadmap/job_result.py:def log_job_result` takes those names.
- The taxonomy holds 22 members, from `src/devops_cli/roadmap/failure.py:67:class FailureClass(StrEnum):` to `src/devops_cli/roadmap/failure.py:91:PLAN_UNREADABLE = "plan_unreadable"`, and `src/devops_cli/roadmap/failure.py:130:ACTION_BY_CLASS: Final[Mapping[FailureClass, FailureAction]] = MappingProxyType(` gives each one action; `src/devops_cli/roadmap/failure.py:120:RETRY = "retry"` is the action of the new class. The change makes 23.
- The set of 23 classes: the 22 staged members keep their action and their fault case, and `form_check` joins with `retry`. Each member is decided: 22 stay covered, and `form_check` is allowlisted with a reason, because the fault suite drives the implement job and only the refine round records this class. Group 4 makes the census name that class and stop when a member has no decision: `tests/roadmap/test_roadmap_faults.py:549:def test_every_failure_class_has_a_fault_case() -> None:` reads `tests/roadmap/test_roadmap_faults.py:552:all_classes = set(FailureClass)`.
- `tests/roadmap/refine/test_roadmap_refine_job_failure.py:302:assert len(failure) <= CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS` is the test that the removed cap makes false, so group 2 replaces it with the assertion that the whole question stays, and `tests/roadmap/test_roadmap_limit_classes.py:198:"CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS": (` is the registry entry that group 2 drops.
- The test module of group 1 and group 3 is `tests/roadmap/refine/test_roadmap_refine_job_failure.py`: `tests/roadmap/refine/test_roadmap_refine_job_failure.py:53:_WHOLE = RefinementProposal(` is the whole reply that the reply with an empty `then` is built from, `tests/roadmap/refine/test_roadmap_refine_job_failure.py:161:def test_a_proposal_that_fails_a_form_check_makes_no_person_wait_and_counts_the_try(` is the case that group 1 updates, and `tests/roadmap/refine/test_roadmap_refine_job_failure.py:87:def chat_structured(self, system: str, prompt: str, schema: type[Any], **_: Any) -> Any:` of `tests/roadmap/refine/test_roadmap_refine_job_failure.py:79:class _Client:` receives each prompt, so group 3 records it there.
- The result-line test that group 4 extends is `tests/roadmap/refine/test_roadmap_refine_job_result.py:71:def test_a_round_logs_the_next_step_of_each_item_and_the_class_of_a_failed_model_call(`, and the two project checks of the taxonomy that group 4 updates are `tests/roadmap/test_roadmap_failure.py:535:def test_the_classes_are_the_twenty_one_of_the_taxonomy() -> None:` and `tests/roadmap/test_roadmap_failure.py:570:assert set(ACTION_BY_CLASS) == set(FailureClass)`.
- `read_file` on `src/devops_cli/ai/tasks/roadmap_refine_proposal.md` lines 1 to 17 showed that its first paragraph describes the key as the findings of a refusal and its ninth paragraph tells the model to fix each finding, so group 3 extends both to the failure of the earlier try.
- The `search_code` answer for `CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS` lists, outside `openspec/changes/archive/`, `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_job_failure.py` and `tests/roadmap/test_roadmap_limit_classes.py`; the answer for `CONST_ROADMAP_REFINE_JUDGE_FINDINGS_MAX_CHARS` adds `docs/roadmap/refine.md` at `docs/roadmap/refine.md:125:at most 2,000 characters`, and `docs/ROADMAP_WORKFLOW.md:132:The next round gives them to the model` names the same key. Each of those files sits in the `changes` of groups 1 to 5.
- Preconditions of the functions that the plan calls: `plan_refine` needs a checkout of the repository (the `git_repo` fixture) and `apply_refine` needs a store client (`InMemoryRoadmapStore`); no call needs a network or a service client. `form_check_details`, `_judge_findings` and `log_job_result` need no precondition.
- The plan introduces no command and no verify program: each `verify` runs `uv run devops ci test` with paths or `uv run devops ci docs`, and the runner image holds `uv`, `devops` and `pytest`. A failing test gives the class `test` and a missing tool gives `ci_infra`. The pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`.
- The finding of `problem` is fixed: the decision now cites the failure class at its own line, `src/devops_cli/roadmap/refine/refine.py:427:class JobFailure:`, which `search_code` returned as its only hit for the class name, and its members are cited at `src/devops_cli/roadmap/refine/refine.py:433:checks: tuple[JobCheck, ...]`. The plan adds no member to the class.
- not checked in this run: the related items #6193, #6196, #2562 and the closed items #6106, #6090, #6043 and #5954; the context lists no overlap, no metric sender and no issue dependency, so `dependencies` is empty.
- Group 4 is the widest group with 5 files, and no group creates a file, so each step fits the budget with the files it changes.

## Existing Tool Considered

pydantic/pydantic-ai (MIT, maintained, last activity 2026-11-18) is already in use, and the alternatives check of the issue body records the verdict `in-use`: it names the failing field path of a structured reply and sends the error text to the next model round. The record detail, the failure class and the result line stay project code, and the change adds no library.

## Dependencies

None.
