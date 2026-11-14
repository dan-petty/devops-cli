# Proposal

## Why

The stage job leaves out an item whose branch is on origin, so a draft plan that fails a check, or whose files main changed, has no way back (#3387). After a draft plan with placeholder text opened for #3307, `devops roadmap explain 3307` gave the reason of a pushed branch, and a person had to edit or abandon the draft. The job must replace its own bad plan on the branch it already made.

## What Changes

- Add the member `RESTAGE` with the value `stage.restage` to `class StageRecordKey` in `src/devops_cli/roadmap/stores/store.py`, with its sentence in the class docstring.
- Add `src/devops_cli/roadmap/stage/stage_held.py` with the pure rule that decides whether the draft plan of a held item is replaced, and with the record of one re-stage.
- Read the one draft pull request of a held item in `src/devops_cli/roadmap/stage/stage_held.py` with `held_draft`: its draft state, its unresolved review threads, the paths of its branch outside the change folder, and the problems that the plan check finds in its change files.
- Narrow `_held` in `src/devops_cli/roadmap/stage/stage.py` so that a failing draft no longer holds the item, and carry the replaced draft on `class StageTarget`.
- Push the new plan commit to the taken-over branch with a lease on the recorded `stage.sha`, because `_rebase_onto_default` can rewrite the branch tip, and set the title and body of the same draft with `update_pull`.
- Name the replaced draft in the comment of the item and record the re-stage in `stage.restage`, so that one re-stage is the bound.
- Add the cases of the re-stage and of the three holds to `tests/roadmap/stage/test_roadmap_stage_selection.py`.
- State the narrowed held rule and the replaced draft in `docs/ROADMAP_WORKFLOW.md` and in `CONTEXT.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/selection`: The stage job re-stages a failing draft plan once, The job leaves out the items it must not stage
- `roadmap-stage/round`: The stage job replaces a draft pull request in place, The comment and the record of a staged item

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stage/stage_held.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_held.py`, `tests/roadmap/stage/test_roadmap_stage_held_read.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`, `tests/roadmap/stage/test_roadmap_stage_restage.py`

## Feasibility

- The probe line reads, word for word: "The path `src/devops_cli/roadmap/stage.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/ai/spend/stage.py`, `src/devops_cli/roadmap/stage/stage.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it."
- The probe line reads, word for word: "The path `tests/roadmap/test_roadmap_stage_selection.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_selection.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it."
- The probe line reads, word for word: "The path `src/devops_cli/roadmap/stage/stage.py` is a file of the staging commit." The premise of the issue stands at the moved path, so the plan uses it and plans no code that compensates for the old one.
- The probe line reads, word for word: "The path `tests/roadmap/stage/test_roadmap_stage_selection.py` is a file of the staging commit." The plan adds its cases there.
- `list_files` of `src/devops_cli/roadmap/stage` showed no `stage_held.py`, and showed `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_rejected.py` and `src/devops_cli/roadmap/stage/stage_specs.py`, so the module of the rule is new and sits in the stage package.
- `list_files` of `tests/roadmap/stage` showed `tests/roadmap/stage/test_roadmap_stage_selection.py` and `tests/roadmap/stage/test_roadmap_stage_apply.py`, and no `test_roadmap_stage_held.py`, no `test_roadmap_stage_held_read.py` and no `test_roadmap_stage_restage.py`, so those three test modules are new.
- `search_code` for `def _held` showed `src/devops_cli/roadmap/stage/stage.py:707: def _held(self, item: Item) -> str | None:`, the rule that the selection reads and that group 3 narrows.
- `read_file` of `src/devops_cli/roadmap/stores/store.py` lines 227-281 showed `src/devops_cli/roadmap/stores/store.py:227:class StageRecordKey(StrEnum):` and `src/devops_cli/roadmap/stores/store.py:258: BRANCH = "stage.branch"`, and no key of a re-stage, so group 1 adds `RESTAGE`.
- `list_files` of `tests/roadmap/stores` showed `tests/roadmap/stores/test_comment_repeat.py`, a test of the store module that group 1 changes; group 1 lists it in `reads` and runs it in `verify`.
- The fault of the check is corrected: the task of group 2 now names `src/devops_cli/roadmap/stage/stage_held.py`, the file it changes, and the head-commit files it reads in code spans, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/github/client.py` and `src/devops_cli/github/pr_threads.py`, so the pack of that step holds files.
- `search_code` for `def folder_problems` showed `src/devops_cli/roadmap/plan_check.py:480:def folder_problems(folder: PlanFolder) -> tuple[StageProposal | None, list[PlanProblem]]:`, the one function that runs the plan check on the change files of a folder.
- `search_code` for `def read_change` showed `src/devops_cli/roadmap/plan_read.py:599:def read_change(files: Mapping[str, str]) -> StageProposal:`, the reader that turns the change files of a branch into a proposal.
- `search_code` for `def read_draft` showed `src/devops_cli/roadmap/implement/implement_pull.py:251:def read_draft(`, the reader of draft readiness of the implement job; the new stage reader is named `held_draft`, so the plan copies no existing name.
- `search_code` for `def select_stageable` showed `src/devops_cli/roadmap/stage/stage.py:807:def select_stageable(` and `class StageTarget` showed `src/devops_cli/roadmap/stage/stage.py:408:class StageTarget:`, so group 3 adds the field to that class and the argument to that function.
- `read_file` of `src/devops_cli/roadmap/stage/stage.py` lines 807-866 showed the verdict that returns `_target_of(item)`, so group 3 fills the replaced draft there and passes `draft_of` into `_Judge`.
- `read_file` of `src/devops_cli/roadmap/stage/stage.py` lines 2641-2687 showed `src/devops_cli/roadmap/stage/stage.py:2641:def read_stage_selection(` with the lambda that gives `holder_of`, where group 3 passes `draft_of`.
- `search_code` for `def _commit_and_push` showed `src/devops_cli/roadmap/stage/stage.py:3168:def _commit_and_push(path: Path, change: StagedChange) -> str:`, the push that group 4 gives the lease.
- `search_code` for `def update_pull` showed `src/devops_cli/github/client.py:454: def update_pull(self, repo: str, number: int, *, title: str, body: str) -> None:`, the write that sets the title and body of the replaced draft.
- `search_code` for `def get_compare_files` showed `src/devops_cli/github/client.py:499: def get_compare_files(self, repo: str, base: str, head: str) -> CompareFiles:`, the read of the paths of the branch.
- `search_code` for `def list_pr_review_threads` showed `src/devops_cli/github/pr_threads.py:362:def list_pr_review_threads(`, the read of the review threads with their resolved state.
- `issue_holder` needs a checkout of the repository: it reads the branches of origin through `read_remote_heads` of `src/devops_cli/git/worktree_add.py`.
- `held_draft` needs a checkout of the repository, a client of the GitHub session of the process, and a network: it reads the branch, its changed paths, its change files and its review threads.
- `get_pull_status`, `get_compare_files`, `get_file_at` and `update_pull` need a client of the GitHub session of the process.
- `list_pr_review_threads` needs a client of that session and a network: it sends the GraphQL query of the review threads.
- `folder_problems` needs a checkout of the repository: it packs the files that each task names from the checkout that its `PlanFolder` carries.
- `read_base_specs` needs a checkout of the repository: it reads the base specs at the default branch.
- `check_proposal` needs no checkout, no client and no network of its own: its caller hands it the proposal, the known capability names and the tree.
- The first check against the real system is `uv run devops roadmap explain 3307`, which must name the item as due while its draft plan fails the plan check. The second is `uv run devops roadmap stage --item 3307 --dry-run`, which must list the read of the draft and its update and make no request.
- The plan introduces no command and no verify program: every verify runs `uv run devops ci test` or `uv run devops ci docs`, whose programs `pytest` and `devops` are in the runner image. A failing verify has the failure class `test`, and no program is `NOT_IN_RUNNER`. The pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and every capability dropped, and the plan writes only the source, the tests and the documents.
- The plan relies on no bound of a constant of the staged tree: the record key is the new member `stage.restage` of `StageRecordKey`, and the plan gives no new name to a constant of the staged tree.
- The plan claims nothing about every member of a set: it reads the change files that the compare of the branch names, and no count of a set decides a hold.
- The tests double only the process edges: the GitHub client, the thread read and the checkout are fakes, and no test reaches the network, a cluster or a real scanner.
- The worktree take-over of a pushed branch and the rebase of group 4 are not checked in this run; the test of group 4 asserts the push with the lease on the recorded commit.

## Existing Tool Considered

No open, maintained tool covers the rule. gidgethub and the client of `src/devops_cli/github/client.py` carry the reads, and `src/devops_cli/github/pr_threads.py` carries the review threads; none of them decides whether a draft holds an item. The rule stays in the repository: about 80 lines of code and 5 test cases in `src/devops_cli/roadmap/stage/stage_held.py`, at about 20k tokens to build, keep and fix, and about 6 hours of elapsed time.

## Dependencies

None.
