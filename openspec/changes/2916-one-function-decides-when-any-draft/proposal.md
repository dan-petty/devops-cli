# Proposal

## Why

Three rules mark a draft pull request ready for review (#2916). The stage row asks `ready_to_mark`, which reads the check runs. The implement job calls `mark_ready` after its watch, which reads the check runs too. `devops pr ready` stops on the failed and running checks of the merge-readiness verdict. No rule reads the task groups of the change, so a partial implement pull request (#2801) passes all three. A person must then find it in review.

This change adds one function, `draft_readiness`, for four kinds of pull request: stage plan, implement, agent and person. The stage row, the implement job and `devops pr ready` ask it. `devops pr check-readiness` adds its refusal as a blocker that names the unticked group. The model evaluator of #2867 plugs in through the `extra_checks` argument.

## What Changes

- Add to `src/devops_cli/roadmap/implement_pull.py` the types `DraftKind`, `Answer`, `Readiness`, `ChangeFacts` and `Draft`, and the function `draft_readiness(draft, extra_checks=())`. A stage plan is complete when opened. An implement pull request is complete when every task group is ticked and the change is archived. An agent's or a person's pull request is complete when `declared` is true. Then the check runs decide: a failed or unread check refuses, a running check waits.
- Add `kind_of`, which reads the kind from the record of the item, and `read_draft`, which reads the item named by the head branch and the `tasks.md` of the pull request head.
- Delete `ready_to_mark` and `StageDraft` of `stage_ready.py`. The stage row asks `draft_readiness`.
- Make `_ready` of the implement job ask `draft_readiness` before `mark_ready`. A refusal or a wait stops the item with its reason.
- Delete `_ready_check_blockers` of `commands/pr.py`. `devops pr ready` asks `draft_readiness` and keeps its exit codes: 1 for a refusal, 8 for a wait. `--force` skips the question.
- Add the blocker kind `READINESS`. `devops pr check-readiness` adds one blocker when the function refuses an implement pull request, and the blocker names each unticked group.
- Add the phrase of the unticked group to the plan-defect rule of `failure.py`, so the stop of an unticked group is a `plan_defect`.
- Say it in the documents.
- The change alters what two commands print and when the Service marks a pull request, so it has a spec delta.
- The change fits one pull request: six groups, one step each.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: One function decides when a draft pull request is ready, The kind of a pull request comes from the record of its item, A pull request that passes its checks is marked ready
- `roadmap-stage`: One function decides, and one function marks
- `pr-merge-readiness`: pr ready asks the readiness function, check-readiness names the unticked group

## Impact

- Code: `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/roadmap/stage_ready.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_draft_readiness.py` (new), `tests/roadmap/test_roadmap_stage_ready.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/commands/test_pr.py`
- Documents: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md`, `CONTEXT.md`, `k8s/README.md`, and the generated `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md` and `README.md`
- Deleted: `ready_to_mark`, `StageDraft`, `_ready_check_blockers`, and the test `test_ready_to_mark_is_true_for_passing_checks_only`, whose cases move into the table test.
- Left as they are: the request plans `plan_pr_ready` and `plan_pr_check_readiness` in `github/pr_plans.py`. Each has one caller (`commands/pr.py:1355`, `:1621`), no test names them, and they list the first requests only, as they do today for the closing-issue and status reads. The MCP exposure table (`CONST_MCP_EXPOSURE_TABLE`) stays, since no command or option is added.
- Left alone on purpose: `devops pr monitor`. It maps the verdict kinds to exit codes and never reads the new kind.

## Dependencies

- #3049 (open, plan PR #3183) gates `_ready` on a review of the diff and writes the review result as the input of `ready_to_mark`, which this change deletes. Both change `_ready` in `implement_run.py`. Merge this change first. #3049 then adds its review as one entry of `extra_checks`. Its change folder adds a new capability and modifies no requirement of this change, so `devops openspec check` finds no overlap.
- #2867 (open) is the user of `extra_checks`. Its acceptance criterion "the check-only behavior is removed by this change" then refers to the checks rule of `draft_readiness`.
- #3098 (open) says a partial draft is ready only when every group is done. `draft_readiness` is the check it needs.
- #2877 (open, plan merged as #3168, active change `2877-the-implement-job-watch-reads-commit`) makes the watch read check runs only. `_ready` reads check runs with `read_check_runs` too, so the two agree. `devops pr ready` keeps the commit statuses, as that plan says.
- #2585 (open, active change `2585-check-readiness-warns-when-a-pull`) adds an advisory to the verdict in `merge_readiness.py` and `commands/pr.py`. Its requirements are ADDED, mine are other names. Expect a text merge in `check_readiness`.
- #2530 (open) changes how `check-readiness` reads the file list. `read_draft` reads the list through `get_pull_files` only for an implement pull request, so the fix of #2530 does not change it.
- #3235 (open) asks to flag `pr_check_readiness` as not read-only. This change adds only reads to the command, so the flag is the same either way.
- #2777 (open, plan PR #3169) labels the pull requests of the jobs in `_pull_request`, not in `_ready`. No overlap.
- #2908 is the tracker. #2882 and #2865 (closed) built the stage row.
- Searched with `gh api -X GET search/issues -f q='repo:dan-petty/devops-cli is:open is:issue <word>'` for `2916`, `draft_readiness`, `ready_to_mark`, `mark_ready`, `stage_ready` and `check-readiness`, and the same with `is:pull-request`.

## Feasibility

- The three rules exist on `origin/main` (4571d5f3). `git grep -n 'mark_ready\|ready_to_mark' -- src` gives: `implement_pull.py:128` (`def mark_ready`), `implement_run.py:709` (the call in `_ready`), `stage_ready.py:64` (`def ready_to_mark`), `:109` (its call), `:114` (`mark_ready(repo, number)`). The body of `ready_to_mark` is one line, `stage_ready.py:68: return draft.checks.is_passing`. `_ready` at `implement_run.py:707-709` reads no check and no task: `execute` calls `_checks(pull)`, then `_ready(pull)` (`:382-383`). `commands/pr.py:1279` is `_ready_check_blockers`, and `:1301` calls it.
- No rule reads the tasks. `grep -rn 'tasks.md' src/devops_cli/github src/devops_cli/commands/pr.py src/devops_cli/roadmap/grounding.py` prints nothing (exit 1). `GROUNDING_RULES` (`grounding.py`) has nine rules. The nearest is `archives_its_change`, which asks only for a file in the archived folder.
- A partial implement pull request is caught today in two places, both late. `openspec validate --archived`, which `devops openspec check` runs, fails an archived change with an unticked task. I copied `openspec/` to a scratch folder, set one task of an archived change to `[ ]` and ran `openspec validate --archived`: `✗ change/2026-11-02-9999-probe-partial`, `✗ 1 incomplete task (0/1 completed)`, `Totals: 506 passed, 1 failed (507 items)`. The step of a group stops the item when a task of the group stays unticked (`implement_step.py:744-749` and `:793`, message `implement_stop_unticked`). This change adds the early, named refusal at the two readiness commands and one decider. It does not add the first catch.
- The existing requirement conflicts with the plan. `openspec/specs/roadmap-stage/spec.md:412` says "`ready_to_mark` SHALL be the only function that decides", and its scenario at `:419` replaces `ready_to_mark` in a test. So the spec delta modifies that requirement. The test that replaces it is `tests/roadmap/test_roadmap_stage_ready.py:342`.
- `check-readiness` cannot call the function from the verdict module. I added `from devops_cli.roadmap.implement_pull import mark_ready` to `github/merge_readiness.py` in a scratch tree and ran `uv run python -c "import devops_cli.github.merge_readiness"`: `ImportError: cannot import name 'CHECK_FAILURE_KINDS' from partially initialized module 'devops_cli.github.merge_readiness' (most likely due to a circular import)`. The cause is `implement_pull.py:24` (`from devops_cli.github.pr_monitor import ...`) and `pr_monitor.py:24` (`from devops_cli.github.merge_readiness import`). I reverted it. So the commands call the function, not `assess_merge_readiness` (`merge_readiness.py:506`), which takes a REST payload and has no kind and no item.
- The check rule needs no new code. `CheckVerdictSummary.exit_code` (`check_verdict.py:106-120`) gives 1 for a failed, cancelled or unread check, 8 for a running one and 0 else. `_judge_checks` (`merge_readiness.py`) maps the same buckets to `CHECKS_FAILING`, `CHECKS_UNREAD` and `CHECKS_PENDING`. `_synthesize_check_items` (`check_verdict.py:359-366`) turns a commit with no check run into one pending check named `no checks reported`, and `read_check_runs` uses it, so an empty head waits. `pr ready` tests pin the codes: `tests/commands/test_pr.py:420-446` expects 0, 8, 1, 1 and 0 for ready, running, failing, unread and an open thread.
- The item of a pull request is found by its branch. `issue_of_branch("feat/2916-one-function-decides-when-any-draft")` gives `2916`, and `issue_of_branch("release-please--branches--main")` gives `None` (`git/branch_form.py:49`, run in the scratch prototype). A plan pull request closes no issue (`openspec/specs/roadmap-stage/spec.md:80`, body `Plans #<issue>`), so the closing-issue read would find nothing for it.
- The text of a file at the head is one call: `GitHubClient.get_file_at(repo, path, ref)` (`github/client.py:322`). The tick state is `parse_task_groups` (`roadmap/step_files.py:141`), which the job already uses (`implement_run.py:446`).
- The taxonomy does not know the new phrase. `classify_failure(FailureEvidence(text="Task group 2, Route the stage row, has a task that is not ticked."))` gives `ci_infra`, whose action is `retry` (`failure.py:72-85`), and a retry cannot tick a task. The same call for `"The change 2916-x is not archived."` and `"A check runs: Lint."` gives `ci_infra`, which is right for both. So the plan-defect rule (`failure.py:176-179`) gets the phrase of the unticked group, and `implement_deadline.py` is not touched: its deadline follows the tool-call lines of the Job log, and the two reads of `_ready` write none.
- Prototype, in `proto3170.py` of the scratchpad, outside the repository: the types, `draft_readiness` and `kind_of`, about 80 lines, run over nine rows. Output: `stage_plan complete -> ready`, `stage_plan check runs -> wait`, `implement complete -> ready`, `implement partial -> refuse 'group 2 (B)'`, `implement not archived -> refuse`, `agent declared -> ready`, `agent not declared -> wait`, `person declared, failed -> refuse`, `person not declared -> wait`, and an extra check that refuses gives `refuse`. `kind_of` gave `implement`, `agent`, `stage_plan`, `person` for the four records. The prototype read no GitHub and wrote nothing in the repository.
- Not verified: how `read_draft` behaves against real GitHub. The test in group 4 fakes the item read and the file read at the edges, as `tests/commands/test_pr.py` fakes GitHub today.

## Existing Tool Considered

The open tool that covers a part of the need is the OpenSpec command already pinned in the project. `openspec validate --archived` fails an archived change with an unticked task (output above), and `openspec list --json` gives `completedTasks` and `totalTasks` (the probe gave `0` and `8` for this change). Both judge a folder. Neither knows the pull request, its kind, its check runs or its group titles, and `validate --archived` runs only in CI after the push, so the author learns it late and without a group name. `parse_task_groups` already names the groups. GitHub's own required checks and draft state cannot read a record of the Service. No open tool decides readiness from the record of an item, so the change builds the function.

Cost of the build, as an estimate: about 60,000 output tokens for the function, the resolver, four call sites and the tests, and about 3 hours of elapsed time for a runner Job and a review. Keep: about 4,000 tokens a quarter. Fix: about 5,000 tokens for each failing case, and the table test names the case. The change deletes `ready_to_mark`, `StageDraft`, `_ready_check_blockers` and one test, and it replaces three rules with one.
