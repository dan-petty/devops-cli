# Proposal

## Why

A roadmap job that needs an owner decision guesses, or it stops with a generic comment that looks like a failure. #3077 adds one owner-question form, one frame for each question hash, an inbox line for the open question, and a resume from the reply of a trusted user, so a step that needs a decision asks and waits.

## What Changes

- Add `src/devops_cli/roadmap/owner_question.py`, one module that renders the owner-question frame, reads its hidden hash block and takes the answer of a trusted author.
- Add `OwnerQuestionRecordKey` with `owner_question.hash`, `owner_question.text` and `owner_question.answer` to `src/devops_cli/roadmap/stores/store.py`, joined to `JobRecord` and to `_JOB_RECORD_KEYS`.
- Make refine post one owner-question frame for each question hash, on the oldest open item that asks it, with a link comment on each other item, and ask one question in one run.
- Resume every covered item with the answer of a trusted reply, and start no run for a reply of a stranger, a bot or the account that the job acts as.
- Post the same form from the stage step and the implement step through `src/devops_cli/roadmap/owner_question.py`.
- Add the `owner` kind to `devops roadmap inbox`, with the item number, the age, the question and the command that answers it.
- Regenerate `docs/commands/roadmap.md` and document the owner question in `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/inbox.md` and `docs/roadmap/refine.md`.
- Add no status label: the status family keeps its six values, and the open question frame is the marker of a question that waits.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-owner-question`: A step posts one owner-question form, One frame for each question hash, One question in one run, One form module for refine, stage and implement, A trusted reply resumes the covered items, An untrusted reply starts no run, The open frame is the marker and no status label is added

### Modified Capabilities

- `roadmap-inbox`: The inbox lists each open owner question

## Impact

- Code: `src/devops_cli/roadmap/owner_question.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/commands/roadmap.py`
- Documents: `docs/commands/roadmap.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/inbox.md`, `docs/roadmap/refine.md`
- Tests: `tests/roadmap/test_owner_question.py`, `tests/roadmap/refine/test_roadmap_refine_owner_question.py`, `tests/roadmap/refine/test_roadmap_refine_owner_answer.py`, `tests/roadmap/stage/test_roadmap_stage_owner_question.py`, `tests/roadmap/implement/test_roadmap_implement_owner_question.py`, `tests/roadmap/test_roadmap_inbox.py`

## Feasibility

- The probe lines confirm the cited paths at the staging commit, word for word: "The path `src/devops_cli/roadmap/trust.py` is a file of the staging commit.", "The path `src/devops_cli/roadmap/refine/refine.py` is a file of the staging commit." and "The path `docs/ROADMAP_WORKFLOW.md` is a file of the staging commit."
- The citation finding is corrected. `read_file("docs/ROADMAP_WORKFLOW.md")` from line 300 to 320 showed `docs/ROADMAP_WORKFLOW.md:311:Write the generated documents in the docs directory of the checkout`, which is the step that writes a generated page, and this citation holds no nested code span, so the check reads the text of the line.
- The finding on the limit registry is corrected. `read_file("tests/roadmap/test_roadmap_limit_classes.py")` showed `tests/roadmap/test_roadmap_limit_classes.py:47:("prefix", "CONST_ROADMAP_", "tests/roadmap/test_roadmap_limit_classes.py"),`, the registry entry of that constant prefix, so group 1 reads that test and a task of group 1 names it, and no group adds a limit constant.
- The finding on the store test is corrected. Group 1 reads `tests/roadmap/stores/test_comment_repeat.py`, whose case `tests/roadmap/stores/test_comment_repeat.py:190:[marker for marker, _ in COMMENT_JOBS] == list(CONST_ROADMAP_JOB_COMMENT_MARKERS),` holds the job markers equal, and `read_file("src/devops_cli/roadmap/stores/store.py")` showed `src/devops_cli/roadmap/stores/store.py:731:_JOB_RECORD_KEYS = frozenset(`, the set that the new key family joins.
- The finding on the run module is corrected. Group 3 changes `src/devops_cli/roadmap/run.py` and reads `tests/roadmap/implement/test_roadmap_implement_deadline.py`, which `list_files("tests/roadmap/implement")` listed.
- The finding on the stage module is corrected. Group 4 changes `src/devops_cli/roadmap/stage/stage.py` and reads `tests/roadmap/stage/test_roadmap_stage_apply.py`, which `list_files("tests/roadmap/stage")` listed.
- The finding on the labels file is corrected. No What Changes item names `.github/labels.yml` now, because no group changes it: `.github/labels.yml:4:holds none of them.` says that the package declares the workflow labels, so the change adds no label there.
- The issue body asks for a `status/needs-input` label and for a per-item setting, and its own accepted scope (the `devops-roadmap-refine` block) replaces both: "The open frame is the marker, so the change adds no status label." The plan adds no label and no setting, so it compensates for nothing and asks a person for no decision that the scope took.
- The status family stays as it is: `src/devops_cli/config/constants.py:3754:CONST_ROADMAP_STATUS_VALUES: Final[tuple[str, ...]] = (` holds six members, `New`, `Ready`, `Planned`, `In Progress`, `In Review` and `Blocked`, so the workflow-document invariant keeps passing and no seventh label exists.
- The staged values of the constants that the plan relies on: `src/devops_cli/config/constants.py:3305:CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM: Final[int] = 2`, `src/devops_cli/config/constants.py:3306:CONST_ROADMAP_REFINE_COMMENT_CAP_WINDOW_HOURS: Final[int] = 24`, `src/devops_cli/config/constants.py:3309:CONST_ROADMAP_REFINE_COMMENT_MARKER: Final[str] = "<!-- devops roadmap refine: next step -->"` and `src/devops_cli/config/constants.py:3808:CONST_ROADMAP_STAGE_COMMENT_MARKER: Final[str] = "<!-- devops roadmap stage -->"`. The frame and the link comment start with the marker of the job that posts them, so the cap of 2 comments in 24 hours counts them.
- `src/devops_cli/config/constants.py:3853:CONST_ROADMAP_JOB_COMMENT_MARKERS: Final[tuple[str, ...]] = (` stays as it is. `read_file("src/devops_cli/roadmap/stores/comment_repeat.py")` showed `COMMENT_JOBS` in that same order, and `tests/roadmap/stores/test_comment_repeat.py:190:[marker for marker, _ in COMMENT_JOBS] == list(CONST_ROADMAP_JOB_COMMENT_MARKERS),` holds the two lists equal, so the plan adds no job marker: each frame starts with the marker of the job that posts it.
- `read_file("src/devops_cli/roadmap/inbox_kind.py")` showed `src/devops_cli/roadmap/inbox_kind.py:11:class InboxKind(StrEnum):` with 13 members and `PERSON` last, and `read_file("src/devops_cli/roadmap/inbox.py")` showed `src/devops_cli/roadmap/inbox.py:384:def read_inbox(` with `src/devops_cli/roadmap/inbox.py:414:jobs=tuple(line for line in ordered if line.kind is not InboxKind.PERSON),`, so the new `owner` kind is the 14th member and the split of `read_inbox` puts its line in the people's list.
- `read_spec("roadmap-inbox")` listed 16 requirement names and none names an owner question, so the plan adds one requirement there. `read_spec("roadmap-author-trust")` shows that the trust set is already defined there, so the plan adds no requirement there and the resume rules live in the new capability.
- `file_symbols("src/devops_cli/roadmap/trust.py")` gave `src/devops_cli/roadmap/trust.py:64:def is_person_comment(comment: IssueComment, actor: str | None) -> bool:` and `trusted_replies` at line 81, so the trust rule and the reply reader exist already and the new module calls them.
- `RoadmapStore.open_items()` needs a client of GitHub for the repository: `read_inbox` calls it at `src/devops_cli/roadmap/inbox.py:398:items = store.open_items()`, and the owner line reads the job record of each open item from that answer.
- `RoadmapStore.comments_on(number)` needs a client of GitHub for the repository; refine calls it to find the frame and the replies after it.
- `RoadmapStore.comment(number, body)` needs a client of GitHub for the repository; refine, stage and implement call it to post the frame and a link comment.
- `RoadmapStore.set_marks(item, marks)` needs a client of GitHub for the repository; refine, stage and implement call it to write `owner_question.hash`, `owner_question.text` and `owner_question.answer`.
- `hash_text(text)` and `is_person_comment(comment, actor)` need no checkout, no client and no network, and `hash_text` is the one hash of the repository's text at `src/devops_cli/roadmap/body_hash.py:def hash_text`.
- The plan introduces no command and no verify program: every `verify` runs the existing `uv run devops ci test` row or the existing `uv run devops ci docs` row, whose check is `src/devops_cli/commands/ci.py:884:cmd=["uv", "run", "devops", "docs", "check"],`, so no failure class and no runner capability is new. The runner image holds `uv`, `python`, `pytest`, `devops` and `gh`, and the new tests reach GitHub only through the fake store in `tests/support/`, so they need no network, no cluster and no scanner, and the pod keeps `readOnlyRootFilesystem: true`.
- The new module `src/devops_cli/roadmap/owner_question.py` and the four new test modules are no files of the staging commit, so the plan lists them in `creates`.
- The first check against the real system needs a client of GitHub: `uv run devops roadmap inbox --kind owner` lists one line for an item whose record holds `owner_question.hash` and no `owner_question.answer`, with the question and the command `gh issue comment <number> --body "<answer>"`.
- The next check needs a client of GitHub: after a reply from a trusted user, `uv run devops roadmap inbox --kind owner` shows no line for that item, and the job record of the item holds `owner_question.answer`.
- The cost is written in `existing_tool`: about 220k tokens and 40 hours of work for the code that the change builds itself.

## Existing Tool Considered

LangGraph (https://github.com/langchain-ai/langgraph, MIT, maintained, last commit 2026-11-11) covers the pause and the resume of a run: a run stops at a step, a checkpointer keeps the state, and the human reply returns as the resume value. The alternatives check of 2026-11-04 gave `partly`. It has no GitHub transport, no inbox line, no trust check and no hash rule, so the change builds that plumbing itself: about 220k tokens to build, about 40 hours of work, about 12k tokens for each of about 4 fix rounds, and about 4k tokens a month to keep. The change deletes no internal code.

## Dependencies

- #2968: the inbox gauges send one series for each kind of `InboxKind` and change `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/commands/roadmap.py` and `src/devops_cli/roadmap/inbox_kind.py`, the three files that the owner line also touches, so the gauge set and the new kind meet in the same enum.
- #4805: the question resolver reads the open question frames and the `owner_question` record keys that this change writes, so it shares `src/devops_cli/roadmap/owner_question.py` with this item and its answer step lands after this item.
