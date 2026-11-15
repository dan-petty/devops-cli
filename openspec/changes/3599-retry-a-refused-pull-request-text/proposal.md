# Proposal

## Why

The implement job stops an item when the form check refuses the body of its pull request. It has no model step for that body, so a body that the model can repair stops the item at the first refusal and waits on a person. #3599 asks for one retry: send the problems to the model, rebuild the body, write it when it passes, and stop only on a second refusal with the refused-reply failure class.

## What Changes

- Add `form_body_cut` to the messages, and a rule in `_text_problems` of `src/devops_cli/roadmap/pull_form.py` that refuses a body whose text above `Closes` or `Plans` ends with `...` or `…`.
- Add `refused_reply` to `FailureClass` with the action `WAIT`, and its row to the class table of `docs/ROADMAP_WORKFLOW.md`.
- Add `src/devops_cli/roadmap/pull_retry.py` with `retried_body`, which rebuilds a refused body once from the model reply and raises `RefusedPullReply` on a second refusal.
- Add the prompt `src/devops_cli/ai/tasks/roadmap_implement_body.md`, which edits the refused text, keeps its facts and writes no cut mark.
- The implement job rebuilds a body that `build_body` refuses one time, writes the rebuilt body, and stops with `refused_reply` on a second refusal.
- The implement job takes the model call as the keyword `rewriter`, as it takes `splitter`, so the tests reach no network.
- Edit `docs/roadmap/implement.md` to state the one retry and the second refusal.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pull-request-form`: A body text that ends with a cut mark is refused
- `roadmap-failure-taxonomy`: The failure classes, One default action for each class
- `roadmap-implement-job/pull-request`: A refused body is rebuilt once, The job rewrites the pull request after the push

## Impact

- Code: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/pull_retry.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/commands/roadmap.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/ai/tasks/roadmap_implement_body.md`, `docs/roadmap/implement.md`
- Tests: `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_pull_retry.py`, `tests/roadmap/implement/test_roadmap_implement_body_retry.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`

## Feasibility

- The premise holds at `src/devops_cli/roadmap/implement/implement_run.py:1572:return build_body(why=self._why(change, room), issue=self.number, change=change)`, and the `except ValidationError` below it raises `_StopError`, so a refused body stops the item with no model call today.
- The review is right that the form check refused no cut mark in a body: the cut rule sits only in the title path, at `src/devops_cli/roadmap/pull_form.py:190:problems.append(texts.form_summary_cut)`, and `src/devops_cli/roadmap/pull_form.py:def _text_problems` holds no such rule. This plan adds the rule in group 1.
- The new rule goes at the end of `src/devops_cli/roadmap/pull_form.py:def _text_problems`, which `src/devops_cli/roadmap/pull_form.py:def body_problems` and `plan_body_problems` both call, so one rule covers the delivery body and the plan body.
- The title rule already refuses a cut summary, through the message `src/devops_cli/lang/en/messages.py:1608:form_summary_cut: str = (` and `src/devops_cli/roadmap/pull_form.py:def _summary_problems`.
- The probe line reads: The path `src/devops_cli/roadmap/pull_form.py` is a file of the staging commit.
- The probe line reads: The path `src/devops_cli/roadmap/messages.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/lang/en/messages.py`. No commit in the history deleted or renamed it.
- The probe line reads: The path `src/devops_cli/roadmap/implement_run.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_run.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.
- The probe line reads: The path `openspec/changes/archive/2026-11-02-3198-pull-request-form-check/design.md` is a file of the staging commit.
- The probe line that says Not probed names `tests/roadmap/test_roadmap_pull_form.py`, `build_body`, `build_plan_body` and `is_placeholder`; this run listed `tests/roadmap/test_roadmap_pull_form.py` and read `src/devops_cli/roadmap/pull_form.py`, so those names are checked here.
- `read_file` on lines 57 to 140 of `src/devops_cli/roadmap/failure.py` showed `src/devops_cli/roadmap/failure.py:class FailureClass` with twenty members and the one table `ACTION_BY_CLASS` with twenty rows, so the plan adds one member and one row.
- `read_file` on lines 470 to 560 of `tests/roadmap/test_roadmap_failure.py` showed two tests that pin the class set and the actions: `tests/roadmap/test_roadmap_failure.py:482:def test_the_classes_are_the_twenty_of_the_taxonomy() -> None:` and `tests/roadmap/test_roadmap_failure.py:512:def test_the_default_actions_are_the_ones_of_the_design() -> None:`. Group 2 changes both, so its verify does not fail.
- `read_file` on lines 200 to 221 of `docs/ROADMAP_WORKFLOW.md` showed the class table under `docs/ROADMAP_WORKFLOW.md:200:| Class | Default action | Meaning |`, so group 2 adds the row of the new class there in the same group as the enum.
- `read_spec` on `roadmap-failure-taxonomy` with the requirement `One default action for each class` returned its text and the two scenarios `The table` and `A new runner image and a lost test`, so the `modified` entry keeps both names.
- `search_code` for `does_not_clear_a_stop` returned `tests/roadmap/test_roadmap_stop_clear.py:491:def test_a_new_digest_does_not_clear_a_stop_for_a_lost_test(store: InMemoryRoadmapStore) -> None:`, the behavior test of the base scenario `A new runner image and a lost test`, so group 2 names it in `test` and reads `tests/roadmap/test_roadmap_stop_clear.py`.
- `search_code` for `refused_reply` returned hits only in the stage reply records and in the archived changes, and none in `src/devops_cli/roadmap/failure.py`, so the failure class `refused_reply` is new.
- `read_spec` on `roadmap-implement-job/pull-request` with the requirement `The job rewrites the pull request after the push` returned its base text and seven scenarios. That text is 487 characters, so the `modified` entry keeps it word for word and the one retry becomes the added requirement `A refused body is rebuilt once`, whose text is 336 characters.
- `list_files` on `tests/roadmap/implement` showed `tests/roadmap/implement/test_roadmap_implement_job.py`, the existing test module of `implement_run.py`, so group 4 changes it and runs it in `verify` with the new module.
- `list_files` on `tests/commands` showed `tests/commands/test_all_commands_help_dryrun.py`, so group 4 reads it: the command builder gains one keyword and its help and dry run stay the same.
- `list_files` on `tests/support` showed `tests/support/roadmap_implement.py`, which group 4 reads for the fake of the job.
- `file_symbols` on `src/devops_cli/roadmap/retitle.py` showed `GatewayRetitleModel`, `chat_structured` and `build_retitle_model`, the shape that the new module follows, and `src/devops_cli/ai/tasks/roadmap_retitle.md` is the prompt file of that model.
- `search_code` for `splitter=get_llm_client` showed `src/devops_cli/commands/roadmap.py:838:splitter=get_llm_client(task="analysis"),`, so the command builds the retry client where it already builds the splitter.
- The plan relies on the body bound that `src/devops_cli/config/constants.py:3555:CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS: Final[int] = 1000` sets to 1000, and `src/devops_cli/roadmap/pull_form.py` names it `BODY_MAX_CHARS`. The plan gives the bound no new name.
- `build_body`, `body_problems` and `retried_body` need no checkout, no client and no network: they read no file and make no request.
- `GatewayPullBody.rewrite` needs a client of the `analysis` task and a network to the gateway; the job takes it as the keyword `rewriter`, so the tests pass a fake and reach no network.
- `get_llm_client` needs the AI settings of the checkout and a network at run time; the plan calls it only where `src/devops_cli/commands/roadmap.py` already builds the client of the splitter.
- `load_task_prompt` needs a checkout, because it reads `src/devops_cli/ai/tasks/roadmap_implement_body.md` from the tree.
- The verify commands are `uv run devops ci test` on test modules, so the programs are `devops` and `pytest` from the runner image, both installed there; a failing test is the failure class `test`, and the pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`. No program of the plan is `NOT_IN_RUNNER`.
- `uv run devops ci docs` in group 5 uses the same image and the same pod settings, and a failing docs check is the failure class `test`.
- The stage job's plan-body path is not checked: this run read no line of `src/devops_cli/roadmap/stage/stage.py`, so the plan adds the retry to the implement job alone, and the shared rule in `_text_problems` covers the plan body that the stage job builds.
- The first checks on the real system after the merge are `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py`, `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/invariants/test_roadmap_workflow_doc.py`, `uv run devops ci test tests/roadmap/test_roadmap_pull_retry.py`, `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_body_retry.py tests/roadmap/implement/test_roadmap_implement_job.py`, `uv run devops ci docs`, and then one live run `uv run devops roadmap implement --item <n> --confirm`, whose stop comment names `refused_reply` when the rebuilt body is refused twice.
- `#5797` changes `src/devops_cli/roadmap/pull_form.py`; this plan adds one rule there and calls `build_body`, so the two merge in either order and the shared file is the one path to watch.

## Existing Tool Considered

No open library covers the project's own form rules of a pull request text. `pydantic-ai-slim` (MIT, last activity 2026-11-04) retries a structured reply that breaks its schema, which `chat_structured` already does, and it knows nothing of `build_body` or `plan_body_problems`. The change builds one function and one prompt instead: about 45k tokens to build, about 8k tokens each month to keep and fix, and about 2 days of elapsed time.

## Dependencies

- #5797: it changes `src/devops_cli/roadmap/pull_form.py`, which holds `build_body` and `_text_problems`; this plan adds one rule there and calls `build_body`, so the two merge in either order.
