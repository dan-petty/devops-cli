# Tasks

## 1. Read each repository of service.repos by default

Kind: behavior. Reads: `src/devops_cli/commands/roadmap.py` (lines 73, 87 to 93, 891 to 917), `src/devops_cli/roadmap/request_plan.py` (lines 854 to 868), `src/devops_cli/config/settings.py` (lines 1066 to 1100). Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_inbox_command.py`, `tests/roadmap/test_roadmap_inbox_requests.py`.

- [x] 1.1 Write the failing tests first. In `tests/roadmap/test_roadmap_inbox_command.py`, add `test_without_repo_the_inbox_reads_each_service_repo` (the `config` fixture sets `service.repos` to two repositories, and the `roadmap_store_repos` fixture lists the repositories that the store opens), `test_with_repo_the_inbox_reads_that_repo_only`, and `test_without_repo_and_no_service_repos_the_inbox_fails_naming_the_setting`. In `tests/roadmap/test_roadmap_inbox_requests.py`, add `test_the_dry_run_lists_reads_for_each_service_repo_and_no_write`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox_command.py tests/roadmap/test_roadmap_inbox_requests.py` fails on the base, because the command reads the origin of the checkout only.
- [x] 1.2 In `inbox_cmd` of `src/devops_cli/commands/roadmap.py`, read the repository of `--repo`, or each repository of `service.repos` in order. Raise `ConfigurationError` that names `service.repos` when the list is empty and `--repo` is not given. In `inbox_requests` of `src/devops_cli/roadmap/request_plan.py`, take the repository as a parameter that the command calls once for each repository. Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox_command.py tests/roadmap/test_roadmap_inbox_requests.py` passes.

## 2. List the unapplied splits and the alternatives questions

Kind: behavior. Reads: `src/devops_cli/roadmap/inbox.py` (lines 63 to 75, 184 to 215), `src/devops_cli/roadmap/refine.py` (lines 263 to 277, 1196), `src/devops_cli/roadmap/store.py` (lines 134 to 160). Changes: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_inbox.py`.

- [x] 2.1 Write the failing tests first. In `tests/roadmap/test_roadmap_inbox.py`, add `test_an_unapplied_split_has_one_line_with_its_step` and `test_an_alternatives_question_has_one_line_naming_the_tool`, and extend the order test with the new classes. Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py` fails on the base, because the inbox has no line for either wait.
- [x] 2.2 In `src/devops_cli/roadmap/inbox.py`, add `InboxKind.SPLIT` and `InboxKind.ALTERNATIVES` after `REFINE`, with `_split_lines` and `_alternatives_lines` that `read_inbox` adds. Add the headings, subjects and clearing steps to `src/devops_cli/lang/en/messages.py`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py` passes.

## 3. List a draft of a job that is old or whose checks failed

Kind: behavior. Reads: `src/devops_cli/roadmap/store.py` (lines 414 to 424, 730 to 771), `src/devops_cli/roadmap/github_store.py` (lines 206 to 222, 641 to 644), `src/devops_cli/roadmap/memory_store.py` (lines 214 to 230, 518 to 535), `src/devops_cli/github/check_verdict.py` (lines 87 to 88, 374 to 390), `src/devops_cli/roadmap/inbox.py` (lines 120 to 130), `src/devops_cli/roadmap/request_plan.py` (lines 166 to 200). Changes: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/test_roadmap_inbox_requests.py`, `tests/roadmap/test_roadmap_store_contract.py`.

- [x] 3.1 Write the failing tests first. In `tests/roadmap/test_roadmap_inbox.py`, replace `test_a_draft_of_a_job_is_not_listed_and_is_not_a_persons_pull_request` with `test_a_job_draft_that_waits_for_checks_and_is_newer_has_no_line`, and add `test_a_job_draft_older_than_the_setting_has_one_line` and `test_a_job_draft_with_a_failed_check_has_one_line`. In `tests/roadmap/test_roadmap_inbox_requests.py`, add `test_check_reads_are_listed_only_for_open_job_drafts`. In `tests/roadmap/test_roadmap_store_contract.py`, add `test_open_pulls_carry_the_head_sha_and_their_check_runs_read_by_sha`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py tests/roadmap/test_roadmap_inbox_requests.py tests/roadmap/test_roadmap_store_contract.py` fails on the base.
- [x] 3.2 Add `head_sha` to `OpenPull` in `src/devops_cli/roadmap/store.py`, with the default `""`. Add `failed_checks(head_sha)` to `RoadmapStore`. Read `head.sha` in `_PullPayload` and implement `failed_checks` in `src/devops_cli/roadmap/github_store.py` with `read_check_runs`, raising `GitHubUnreadError` on an unread summary. Implement both in `src/devops_cli/roadmap/memory_store.py`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py` passes.
- [x] 3.3 Add `RoadmapInboxConfig` with `draft_days` and `wait_days` to `src/devops_cli/config/settings.py` as `roadmap.inbox`, with the defaults `DEFAULT_ROADMAP_INBOX_DRAFT_DAYS` and `DEFAULT_ROADMAP_INBOX_WAIT_DAYS` in `src/devops_cli/config/defaults.py`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py` passes once task 3.4 is done.
- [x] 3.4 In `src/devops_cli/roadmap/inbox.py`, read the check runs of each job draft in `read_inbox`, and list a job draft as `InboxKind.DRAFT` when it is older than `draft_days` or its check runs failed. Add `StoreRequests.failed_checks` and the condition `open job draft` to `src/devops_cli/roadmap/request_plan.py`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py tests/roadmap/test_roadmap_inbox_requests.py` passes.

## 4. Mark the old waits, count the classes and filter by class

Kind: behavior. Reads: `src/devops_cli/roadmap/inbox.py` (lines 77 to 88, 286 to 339), `src/devops_cli/commands/roadmap.py` (lines 891 to 917), `src/devops_cli/lang/en/messages.py` (lines 3542 to 3600). Changes: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/test_roadmap_inbox_command.py`.

- [x] 4.1 Write the failing tests first. In `tests/roadmap/test_roadmap_inbox.py`, add `test_a_wait_older_than_the_setting_is_marked`, `test_counts_by_class_lead_the_inbox` and `test_the_class_filter_keeps_one_kind`, and extend `test_each_line_has_its_number_its_age_and_the_step_that_clears_it` with the mark. In `tests/roadmap/test_roadmap_inbox_command.py`, add `test_the_kind_option_keeps_the_lines_of_one_class`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py tests/roadmap/test_roadmap_inbox_command.py` fails on the base.
- [x] 4.2 Add `old` to `InboxLine` and set it in `read_inbox` from `wait_days`. Add a `kinds` parameter to `render_inbox` and print the counts of all lines under the title. Add the option `--kind` to `inbox_cmd` with the type `InboxKind`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py tests/roadmap/test_roadmap_inbox_command.py` passes.

## 5. Document the classes, the repositories and the settings

Kind: other. Reads: `docs/roadmap/inbox.md`, `src/devops_cli/lang/en/help.py` (lines 1569 to 1578). Changes: `docs/roadmap/inbox.md`, `src/devops_cli/lang/en/help.py`, `README.md` when the generator changes it.

- [ ] 5.1 In `src/devops_cli/lang/en/help.py`, state the classes, the default repositories, the option `--kind` and the marks of the command help. Run `uv run devops docs generate --sync-readme`. Verification: `uv run devops roadmap inbox --help` names `--kind`, and `uv run devops ci docs` passes.
- [ ] 5.2 Rewrite `docs/roadmap/inbox.md` for the classes in their order, the repositories that the command reads, the two settings, the counts and the filter. Verification: `uv run devops ci docs` passes.

## Criteria

- Each new class has a test: group 2 and group 3.
- A draft of a job that waits for its checks and is newer than the setting has no line: group 3.
- The rule for a returned item is kept and tested: group 2.
- Without `--repo`, the inbox reads each repository of `service.repos`: group 1.
- Counts by class lead the inbox, and the filter keeps one class: group 4.
- `uv run devops ci` passes: the full gate, run before the archive.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
