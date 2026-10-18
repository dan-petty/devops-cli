# Task: PR readiness exempts a release-process pull request only by the files it changes (#1344)

**Issue**: [#1344](https://github.com/dan-petty/devops-cli/issues/1344)
**Status**: Done
**Milestone**: v0.2.37
**Priority**: priority/p1-high
**Scope**: type/bug, scope/github, scope/release
**Feasibility**: Confirmed on origin with read-only `devops gh api` calls. `pulls/1614/files` (`chore/cut-v0.2.36` into `release/v0.2.36`) lists `CHANGELOG.md`, `docs/ROADMAP.md`, `pyproject.toml` and `uv.lock` as `modified` and 24 `changelog.d/<n>.md` as `removed`, and nothing else. The closed pull requests list `chore/open-v0.2.33-trivyignore`, `-bandit-coverage` and `-fastmcp-log-isolation`, which carried code fixes into `release/v0.2.33` under the old exemption. `compare/de09432a59...main` returns the same 188 files with and without `per_page=1`, and with `per_page=1` one commit instead of two, as GitHub documents (the changed files are on the first page, at most 300 for the whole comparison).

## Description

`devops pr check-readiness` exempted any `chore/open-vX.Y.Z[-slug]` pull request into `release/vX.Y.Z` from grounding, whatever it changed, and held the cut pull request, `chore/cut-vX.Y.Z` into `release/vX.Y.Z`, to grounding, so the v0.2.36 cut (#1614) failed with "closes no issue". The exemption now depends on the files the pull request changes.

- **Which heads** (`src/devops_cli/config/constants.py`). `CONST_RELEASE_PROCESS_BRANCH_RE` matches `chore/cut-vX.Y.Z` and `chore/open-vX.Y.Z`, each optionally followed by `-<slug>`, with a `kind` group (`CONST_RELEASE_PROCESS_CUT_KIND`, `CONST_RELEASE_PROCESS_OPEN_KIND`). A fork, another version, a slug before the version, a non-`chore` head or a head into the default branch is no release-process pull request, as before.
- **What a cut may change** (`src/devops_cli/commands/pr.py`, `_cut_hold`). Every path is a `CONST_RELEASE_CUT_FILES` entry with status `modified`, or a `changelog.d/<n>.md` with status `removed`: exactly what `cut_release` writes. It is judged from the file list `_evaluate_pr_blockers` already reads, so a cut costs no extra request.
- **What a merge of `main` may change** (`_merge_hold`). Every path is a cut file or a file the default branch changed since its merge base with the base, read with one `GET repos/{repo}/compare/{base sha}...{default branch}?per_page=1` (`_read_default_branch_changes`). The compare is read only when the pull request changes a file that is not a cut file.
- **Renames** are judged by both paths (`_paths`), for both kinds. A cut only modifies and removes, so a rename in a cut is never the cut's change.
- **Held to grounding.** A release-process pull request that changes another file gets one blocker naming those files, bounded to `CONST_MAX_ERROR_DETAIL_LENGTH` (`grounding_cut_changes_more`, `grounding_merge_changes_more`), and the usual grounding blockers follow it. An unread file list holds it, and the existing `grounding_files_unread` names that. A compare that fails, returns malformed JSON or no file list, or lists `CONST_GH_COMPARE_FILES_CAP` (300) files holds it, and `grounding_merge_changes_unread` names the failure. A pull request payload that names no default branch sends no compare and is held the same way, the blocker naming the default branch as unknown (`grounding_unnamed_default_branch`, `grounding_no_default_branch`).
- **One list.** `CUT_FILES` moved from `roadmap/close.py` to `CONST_RELEASE_CUT_FILES` beside `CONST_RELEASE_SHARED_FILES`; `roadmap/close.py`, `commands/roadmap.py` and readiness read it.
- **Docs.** The `check-readiness` help, with the generated `docs/commands/pr.md`, `docs/commands/gh.md` and `docs/CLI_REFERENCE.md`; `RELEASE_CYCLE.md` Stage 1 rule 6, `docs/agent/tasks/README.md` rule 5 and `.github/pull_request_template.md`'s Base Branch comment name the release pull request (`release/vX.Y.Z` into `main`), the cut pull request (`chore/cut-vX.Y.Z` into `release/vX.Y.Z`) and the merge of `main` (`chore/open-vX.Y.Z-main`), each with its file rule.

## Acceptance Criteria

- [x] A `chore/cut-vX.Y.Z[-slug]` pull request from this repository into `release/vX.Y.Z` is exempt only when every changed path, both paths of a rename included, is a `CONST_RELEASE_CUT_FILES` entry with status `modified` or a `changelog.d/<n>.md` with status `removed`: `test_a_cut_pull_request_that_changes_only_the_cut_files_is_exempt` (#1614's file list, no `/contents/` and no `/compare/` request), `test_a_cut_pull_request_that_changes_another_file_is_held_to_grounding` (a `src/` file, an added fragment, an edited or removed `changelog.d/README.md`, an added cut file) and `test_a_renamed_file_is_judged_by_both_paths`, in `tests/test_pr_cmd.py`.
- [x] A `chore/open-vX.Y.Z[-slug]` pull request is exempt only when every changed path is a cut file or a file the default branch changed since its merge base with the base branch, read with one compare request: `test_a_merge_of_main_that_changes_only_what_main_changed_is_exempt` (exactly one compare read, `compare/<base sha>...main?per_page=1`), `test_a_merge_of_main_that_changes_only_the_cut_files_reads_no_compare` and `test_a_merge_of_main_with_another_file_is_held_to_grounding`.
- [x] Otherwise grounding applies, and one blocker names the files outside the allowed set, with the usual grounding blockers after it: `test_the_cut_blocker_reads_in_full`, `test_a_merge_of_main_with_another_file_is_held_to_grounding` and `test_the_files_the_blocker_names_are_bounded` (256 characters of the file list).
- [x] An unread file list, a compare that fails or returns 300 files, or a payload that names no default branch applies grounding, and a blocker names the failure: `test_an_unread_file_list_holds_a_release_process_head_to_grounding`, `test_an_unread_or_full_compare_holds_a_merge_of_main_to_grounding` (failed, malformed, no file list, 300 files) and `test_a_merge_of_main_whose_default_branch_is_unnamed_is_held_without_a_compare` (no compare request).
- [x] A fork, another version, a slug before the version, a non-`chore` head or a head into the default branch is held to grounding, as before, and reads no compare: `test_other_branches_are_held_to_grounding` and `test_a_release_process_branch_from_a_fork_is_not_exempt`, for both kinds.
- [x] `CUT_FILES` is gone. `roadmap/close.py`, `commands/roadmap.py` and readiness read `CONST_RELEASE_CUT_FILES`; `tests/test_roadmap_close.py`, `tests/test_roadmap_dry_runs.py` and `tests/test_roadmap_run.py` pass unchanged.
- [x] `RELEASE_CYCLE.md`, `docs/agent/tasks/README.md` and `.github/pull_request_template.md` name the three pull requests, each with its file rule. `rg -n 'chore/cut-vX.Y.Z. into .main' RELEASE_CYCLE.md docs/agent/tasks/README.md` prints nothing.
- [x] `devops docs check` passes with the regenerated command docs.
- [x] `changelog.d/1344.md` records the change under `### Fixed`. `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- Pending a person: `uv run devops pr check-readiness <the v0.2.37 cut pull request>` shows no grounding blocker.

## Decisions and Deviations

- **The merge of `main` reads no compare when it changes only cut files.** Those files are allowed without it, so the compare is read only for a path that is not a cut file, and at most once.
- **One commit per compare page.** GitHub lists the changed files on the first page whatever its size, so `per_page=1` keeps the commits the compare also returns to one (`CONST_GH_COMPARE_COMMITS_PER_PAGE`).
- **A merge of `main` may change a cut file under any status.** `main`'s own changes reach the release branch with whatever status they have, so only the cut pull request is held to `modified` and `removed`.
- **The changed-file parsing is shared.** `_changed_file` takes the name of the API it reads, and `_changed_files` and `_gh_json` read both the pull request's files and the compare's, so a malformed compare is named as the compare's.
- **An unnamed default branch sends no compare.** `_is_release_pr` already reads an empty default branch as unknown; `_read_default_branch_changes` does the same instead of asking for `compare/<sha>...`, which can't succeed, and the blocker says the default branch is unknown rather than leaving its name blank.
- **A flaky service test is fixed here.** `devops ci` failed on a loaded machine in `test_polling_tick_advances_with_injected_fixtures` (`tests/test_server_service.py`), which gave the lane's worker thread a fixed 0.1 s to run the startup poll. It now waits, bounded at 5 s, on the job and the loop's interval sleep, as the other service tests wait on their events. No issue tracks it; it is a test-only change, needed for this pull request's `devops ci` to pass, and has no changelog entry.

## Deliverables

- [x] `src/devops_cli/commands/pr.py`: `_release_process_kind`, `_cut_hold`, `_merge_hold`, `_read_default_branch_changes`, `_release_process_hold`, `_grounding_scope` taking the changed-file read, and the `check-readiness` help.
- [x] `src/devops_cli/config/constants.py`: `CONST_RELEASE_PROCESS_BRANCH_RE` with its `kind` group, `CONST_RELEASE_CUT_FILES`, `CONST_PR_FILE_REMOVED_STATUS`, `CONST_GH_COMPARE_FILES_CAP`, `CONST_GH_COMPARE_COMMITS_PER_PAGE`, and the grounding comment.
- [x] `src/devops_cli/roadmap/close.py` and `src/devops_cli/commands/roadmap.py`: `CUT_FILES` replaced by `CONST_RELEASE_CUT_FILES`.
- [x] `src/devops_cli/lang/en/messages.py`: `grounding_cut_changes_more`, `grounding_merge_changes_more`, `grounding_merge_changes_unread`, `grounding_merge_changes_capped`, `grounding_unnamed_default_branch` and `grounding_no_default_branch`.
- [x] `tests/test_pr_cmd.py`: the release-process tests above, replacing the exemption tests.
- [x] `tests/test_server_service.py`: `test_polling_tick_advances_with_injected_fixtures` awaits its events instead of a fixed pause.
- [x] `RELEASE_CYCLE.md`, `docs/agent/tasks/README.md`, `.github/pull_request_template.md`, and the generated `docs/commands/pr.md`, `docs/commands/gh.md` and `docs/CLI_REFERENCE.md`.
- [x] `changelog.d/1344.md`.
