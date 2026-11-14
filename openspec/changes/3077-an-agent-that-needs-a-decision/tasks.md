# Tasks

## 1. Add the owner-question form module and its record keys

Kind: behavior. Reads: `src/devops_cli/roadmap/trust.py`, `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/comment_repeat.py`, `src/devops_cli/roadmap/inbox.py`, `tests/roadmap/stores/test_comment_repeat.py`, `tests/roadmap/test_roadmap_limit_classes.py`. Changes: `src/devops_cli/roadmap/owner_question.py` (new), `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/test_owner_question.py` (new).

- [x] 1.1 Add a case in `tests/roadmap/test_owner_question.py` for a form that holds the question once, two or three options, a recommendation, the evidence and the hidden hash block, and for the same question and options giving the same hash
  - Verification: `$ uv run devops ci test tests/roadmap/test_owner_question.py` fails on the base
- [x] 1.2 Add `OwnerQuestionRecordKey` with `HASH = "owner_question.hash"`, `TEXT = "owner_question.text"` and `ANSWER = "owner_question.answer"` to `src/devops_cli/roadmap/stores/store.py`, and join it to `JobRecord`, to `_JOB_RECORD_KEYS` and to `__all__`, so `tests/roadmap/stores/test_comment_repeat.py` and the record parse keep passing. Add `QuestionOption` and `OwnerQuestion` to the new module: `hash` is the `hash_text` of the question and the option texts, `render` writes the question once, two or three options with their results, a recommendation, the evidence and the hidden block `<!-- owner-question:<hash> -->`, `frame_hash` reads the hash of a comment, `link_comment` links the frame from another item, and `answer_of` gives the newest comment after the frame that `is_person_comment` accepts. The hidden-block prefix is a text of this module, so no limit constant and no job marker is added, and the registry in `tests/roadmap/test_roadmap_limit_classes.py` stays unchanged
  - Verification: `$ uv run devops ci test tests/roadmap/test_owner_question.py` passes

## 2. Post one owner-question frame from refine

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/owner_question.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_person_wait.py`, `tests/roadmap/refine/test_roadmap_refine_comment_cap.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_owner_question.py` (new).

- [x] 2.1 Add a case in `tests/roadmap/refine/test_roadmap_refine_owner_question.py` for a refine step that posts one frame for its question hash, asks one question in the run, and posts a link comment on the second item that asks the same question
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_owner_question.py` fails on the base
- [x] 2.2 In `step_comment` of `src/devops_cli/roadmap/refine/refine.py`, render a wait on a person as one `OwnerQuestion` frame for the first open question, and leave the other open questions to later rounds, so one run asks one question. Record `OwnerQuestionRecordKey.HASH` and `OwnerQuestionRecordKey.TEXT` with `set_marks`. When an older open item holds a frame with the same hash, post `link_comment` on this item and record the same hash. Both comments start with `CONST_ROADMAP_REFINE_COMMENT_MARKER`, so the cap of `CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM` counts them. Add the texts of the frame and the link to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_owner_question.py` passes

## 3. Resume the covered items on a trusted reply

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/trust.py`, `src/devops_cli/roadmap/owner_question.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/refine/test_roadmap_refine_trust.py`, `tests/roadmap/implement/test_roadmap_implement_deadline.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/refine/test_roadmap_refine_owner_answer.py` (new).

- [x] 3.1 Add a case in `tests/roadmap/refine/test_roadmap_refine_owner_answer.py` for a trusted reply that writes the answer on each covered item and starts its run, and for a reply from another user that writes nothing and starts no run
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_owner_answer.py` fails on the base
- [x] 3.2 Read the answer of the frame with `OwnerQuestion.answer_of`. Write `OwnerQuestionRecordKey.ANSWER` and end the wait on each open item whose record holds the same `OwnerQuestionRecordKey.HASH`, and give the request of each covered item the answer text and the frame reference. Pass the actor of the run in `src/devops_cli/roadmap/run.py` to the round, so `is_person_comment` refuses a bot and the account that the job acts as. A reply that is not trusted records nothing and starts no run
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_owner_answer.py` passes

## 4. Post the form from the stage step

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/owner_question.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`, `tests/roadmap/stage/test_roadmap_stage_item_writes.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_owner_question.py` (new).

- [x] 4.1 Add a case in `tests/roadmap/stage/test_roadmap_stage_owner_question.py` for a group that is still over the budget, where the stage step posts the owner-question form through the module and records the hash and the question
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_owner_question.py` fails on the base
- [x] 4.2 In `_stop_on_budget` of `src/devops_cli/roadmap/stage/stage.py`, post the `OwnerQuestion` frame with `CONST_ROADMAP_STAGE_COMMENT_MARKER` and the question whether to split the group or raise its budget, with the group title and its tokens as the evidence. Record `OwnerQuestionRecordKey.HASH` and `OwnerQuestionRecordKey.TEXT` in the marks that the step already writes. The stage step asks one question and ends
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_owner_question.py` passes

## 5. Post the form from the implement step

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/owner_question.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_owner_question.py` (new).

- [x] 5.1 Add a case in `tests/roadmap/implement/test_roadmap_implement_owner_question.py` for a stop of class `plan_defect`, where the step posts the owner-question form through the module and the record of the item holds the hash and the question
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_owner_question.py` fails on the base
- [x] 5.2 In `stop` of `src/devops_cli/roadmap/implement/implement_run.py`, when the class of the stop is `plan_defect`, post the `OwnerQuestion` frame with `CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER` and the question whether to amend the plan or split the item, with the failing check as the evidence, and record `OwnerQuestionRecordKey.HASH` and `OwnerQuestionRecordKey.TEXT` in the same `set_marks` write as the stop. The step asks one question and ends
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_owner_question.py` passes

## 6. List the open owner question in the inbox

Kind: behavior. Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/commands/roadmap.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/commands/test_all_commands_help_dryrun.py`. Changes: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/commands/roadmap.py`, `tests/roadmap/test_roadmap_inbox.py`.

- [x] 6.1 Add a case in `tests/roadmap/test_roadmap_inbox.py` for an open owner question that the inbox lists with kind `owner`, the item number, the age, the question and the command that answers it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py` fails on the base
- [x] 6.2 Add `OWNER = "owner"` to `InboxKind` after `PERSON`. Add `_owner_lines` to `read_inbox`: one line for each open item whose record holds `OwnerQuestionRecordKey.HASH` and no `OwnerQuestionRecordKey.ANSWER`, with the age, the recorded question text and the clear command `gh issue comment <number> --body "<answer>"`. Change the split of `read_inbox` so the `owner` line joins the people's list beside `InboxKind.PERSON`. Add the heading, the subject and the clear to `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`. Name the owner question in the docstring of `inbox_cmd` and in `HELP.roadmap.inbox_kind`, so the `--kind` help names `owner`, and keep the help case of `tests/commands/test_all_commands_help_dryrun.py` passing
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py` passes

## 7. Regenerate the roadmap command page

Kind: other. Reads: `docs/commands/roadmap.md`, `src/devops_cli/commands/roadmap.py`. Changes: `docs/commands/roadmap.md`.

- [x] 7.1 Run `uv run devops docs generate` after the `--kind` help and the `InboxKind` member change, so `docs/commands/roadmap.md` shows `owner` in the `--kind` choice of `inbox`
  - Verification: `$ uv run devops ci docs` passes
- [x] 7.2 Edit `docs/commands/roadmap.md` through `uv run devops docs generate`, never by hand
  - Verification: `$ uv run devops ci docs` passes

## 8. Document the owner question in the workflow and roadmap pages

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/inbox.md`, `docs/roadmap/refine.md`, `tests/invariants/test_roadmap_workflow_doc.py`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/inbox.md`, `docs/roadmap/refine.md`.

- [ ] 8.1 Describe the owner question in the Refine step of `docs/ROADMAP_WORKFLOW.md` and name the `owner_question` record keys there. Add the `owner` kind and the answer command to `docs/roadmap/inbox.md`, and the one-question rule and the answer path to `docs/roadmap/refine.md`. The status family keeps its six labels, and no label is declared for the owner question
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py` passes
- [ ] 8.2 Edit `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/inbox.md` and `docs/roadmap/refine.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 8: The label is declared in `.github/labels.yml` and in the workflow document (the invariant test passes).
- Group 3: A reply resumes the run in a replay test, and a reply from another user does not.
- Group 6: The question appears in the inbox with the command to answer it.
- Group 2: A question is limited per item (a setting).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
