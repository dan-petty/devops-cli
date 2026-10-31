# Tasks

## 1. Move Clone Destination Parsing
- [x] Move `_extract_url_path` and `_parse_clone_destination` to `parse_clone_destination` in `src/devops_cli/git/operations.py` <!-- id: 1-clone-dest -->
- [x] Update `src/devops_cli/commands/repos.py` to use `parse_clone_destination` <!-- id: 1-repos-cmd -->
- [x] Add unit tests for `parse_clone_destination` in `tests/test_git_operations.py` <!-- id: 1-git-tests -->

## 2. Move Rate Limit Parsing and View Formatting
- [x] Create `src/devops_cli/github/rate_limit_view.py` with `format_reset_time`, `parse_rate_limit_payload`, and `format_rate_limit_rows` <!-- id: 2-rate-limit-module -->
- [x] Update `src/devops_cli/commands/gh.py` to use `devops_cli.github.rate_limit_view` <!-- id: 2-gh-cmd -->
- [x] Add unit tests for rate limit parsing in `tests/test_rate_limit_view.py` <!-- id: 2-rate-limit-tests -->

## 3. Move Branch Update Planning
- [x] Create `src/devops_cli/github/branch_update.py` with `open_prs_argv`, `plan_update_all_prs`, and `plan_update_single_pr` <!-- id: 3-branch-update-module -->
- [x] Update `src/devops_cli/commands/pr.py` to use `devops_cli.github.branch_update` <!-- id: 3-pr-cmd -->

## 4. Move Pull Request Template Invariant Tests
- [x] Create `tests/invariants/test_pull_request_template.py` with template invariant tests <!-- id: 4-pr-template-invariant -->
- [x] Remove template invariant tests from `tests/test_pr_cmd.py` <!-- id: 4-clean-pr-cmd -->
- [x] Add `test_pull_request_template.py` to `docs/TESTING.md` <!-- id: 4-update-docs-testing -->

## 5. Verification
- [x] Run `uv run devops ci` and verify all checks pass <!-- id: 5-ci -->
- [x] Archive change and create draft pull request <!-- id: 5-archive-and-pr -->
