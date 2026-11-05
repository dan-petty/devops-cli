# Proposal

## Why

Issue #3494: `devops roadmap inbox` omits most of the waits that a person must clear. It lists one repository. It shows no unapplied split and no alternatives question. It hides every draft of a job, even a draft whose checks failed or that is old. A person who reads the inbox does not see the questions that wait for an answer. This change makes the inbox list each wait, for each repository of `service.repos`, with counts by class, a filter by class and a mark on each old wait.

## What Changes

- `devops roadmap inbox` reads each repository of `service.repos` when `--repo` is not given. With `--repo`, it reads that repository only. When `service.repos` is empty and `--repo` is not given, the command fails and names the setting (`src/devops_cli/commands/roadmap.py`).
- `InboxKind` gets three classes, in this order after `REFINE`: `SPLIT` (an open New item whose refine next step is `split`), `ALTERNATIVES` (an open New item whose `refine.alternatives_asked` is set) and `DRAFT` (a draft of a job that is older than `roadmap.inbox.draft_days`, or whose head commit has a failed check run). The draft rule that hid every draft of a job is removed (`src/devops_cli/roadmap/inbox.py`).
- `OpenPull` gets the field `head_sha`, read from the pull request listing. `RoadmapStore` gets `failed_checks(head_sha)`, implemented by the GitHub store with `read_check_runs` and by the in-memory store. An unread check run raises `GitHubUnreadError`.
- A new setting group `roadmap.inbox` holds `draft_days` and `wait_days`, both 7 by default (`src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`).
- A line whose wait is older than `roadmap.inbox.wait_days` shows a mark.
- The output starts with the count of lines in each class. The option `--kind` keeps the lines of one class.
- `--dry-run` lists the reads of each repository, and the check-run reads of each open job draft, under the condition that the draft exists. It makes no request.
- The spec delta `openspec/changes/3494-inbox-lists-all-person-waits/specs/roadmap-inbox/spec.md` changes the requirements about the gates, the draft rule and the bounded reads, and adds the requirements of this change. `docs/roadmap/inbox.md` and the help text of the command state the classes and the options.
- The change fits one pull request. It has a spec delta because a command, an option, a message and a setting are observable (`openspec/config.yaml`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-inbox`: the gates of the jobs, the bounded reads of each repository, the draft rule and the marks, counts and filter of the lines are changed or added.

## Impact

- Code: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Tests: `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/test_roadmap_inbox_command.py`, `tests/roadmap/test_roadmap_inbox_requests.py`, `tests/roadmap/test_roadmap_store_contract.py`.
- Documents: `docs/roadmap/inbox.md`, the help of the command in `README.md` when `devops docs generate --sync-readme` changes it.
- Unchanged on purpose: the record keys of `src/devops_cli/roadmap/store.py` (no new key is written), the claim threshold `CONST_ROADMAP_INBOX_CLAIM_DAYS` (a constant of the rule of the spec), and the people's list (`InboxKind.PERSON`).

## Dependencies

- #3483 is in `main` (closed by ce689f43). It gives the first line for a refine person wait, which this change keeps.
- #3478 (filler replies) is not confirmed closed. The line that the inbox shows for a returned item is not quoted as an action until #3478 is repaired. This change quotes no evidence text.
- #2968 and #3077 come after this change: #2968 counts these classes and #3077 adds its class to the inbox.
- #3497 (repeated reads) may need its fix first. Each open job draft adds one check-run read. The number of drafts is small, so this change does not wait for it.

## Feasibility

Checked on `origin/main` d254410c, the base of this branch. Each premise was read from the code at that commit.

- The draft rule of the inbox. `git show origin/main:src/devops_cli/roadmap/inbox.py | sed -n 129p` prints `return None if pull.draft else kind`. A draft of a job is dropped there, so the premise holds.
- The person wait is in the tree. `inbox.py` lines 184 to 215 hold `refine_wait_on_person` and `_refine_lines`. That is the first line for a refine person wait of #3483.
- The unapplied split has no reader. `refine.py:1196` returns `NextStep.SPLIT`. `git grep -n SPLIT origin/main -- src/devops_cli/roadmap/inbox.py` prints nothing, so the inbox never lists a split.
- The alternatives question is recorded. `store.py:154` names `RefineRecordKey.ALTERNATIVES_ASKED`. `refine.py:2079` sets it to the tool when the check verdict is `covers`. `inbox.py` reads no such key. The issue asks to confirm that an alternatives wait holds next step `person`. Not confirmed: `refine.py:560-564` says that the covers question joins the open questions only after a reply, so this change reads the key `alternatives_asked` and not the next step.
- The head commit of a pull request is not read. `OpenPull` (`store.py:414-424`) has no head commit field. `_PullPayload` (`github_store.py:206-222`) reads `head.ref` and no `head.sha`. This change adds both.
- The check runs can be read by commit. `read_check_runs(owner, repo_name, head_sha, *, session)` (`github/check_verdict.py:374`) returns `CheckVerdictSummary`. Its `unread_reason` names a failed read and its `fail_count` (`check_verdict.py:87`) counts the failed runs. The REST path is `/repos/{owner}/{repo}/commits/{sha}/check-runs` (`check_verdict.py:315`).
- The command reads one repository. `_target` (`commands/roadmap.py:87-93`) resolves `--repo` or the origin of the checkout. `inbox_cmd` (`commands/roadmap.py:891-917`) calls `read_inbox` once. `ServiceConfig.repos` is at `settings.py:1069`. The issue gives line 1002, which is stale.
- The live counts of the issue (84 person waits, 35 returned items, 12 splits, 3 alternatives, the drafts of vibes, dreamscaper and dotfiles) are not checked here. This session cannot read the live Service store. The change does not depend on these numbers.
- Not verified: how GitHub answers the check-run request for a draft whose checks never ran. The contract test uses the recorded GitHub fake, which holds the same answer shape.

## Existing Tool Considered

No external tool covers an inbox of the roadmap waits. The existing `devops roadmap inbox` covers the need, and the change extends it. It reuses `read_inbox`, the record keys of `store.py`, `service.repos` and `read_check_runs`. No open tool reads the job records of this repository.

Cost of this build, as an estimate: about 350,000 tokens to build, about 60,000 tokens to keep the classes in step with the refine record keys, and about 10,000 tokens for each new class that refine adds. Elapsed time is about 3 hours, with the CI waits.

The change deletes the draft rule at `inbox.py:129` and its test `test_a_draft_of_a_job_is_not_listed_and_is_not_a_persons_pull_request`. The spec scenario "A draft of a job" is replaced by the requirement on the draft class in the delta.
