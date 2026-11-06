# Proposal

## Why

The SARIF export of a review writes no versionControlProvenance. SARIF 2.1.0 requires a repositoryUri in that object (section 3.23.3). The ToolRun record holds the commit but not the repository. A -dirty commit is not a valid revision of the scanned files (section 3.23.4). See #2101.

## What Changes

- Add repository_uri field to ToolRun, read from the remote.origin.url setting of the checkout with the userinfo stripped. A remote that is malformed, or is not an absolute URI with a host, gives None.
- Write versionControlProvenance in the SARIF export. It holds one entry for each distinct pair of repository URI and clean commit among the records of the tool.
- Change the base requirement of sarif-export that forbids versionControlProvenance.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-tool-runs`: ToolRun repository_uri field
- `sarif-export`: versionControlProvenance in SARIF export (a MODIFIED requirement)

## Impact

- Code: `src/devops_cli/security/tool_executor.py`, `src/devops_cli/security/sarif.py`
- Tests: `tests/ai/test_tool_executor_contract.py`, `tests/security/test_sarif_emission.py`, `tests/security/test_scanner_tool_executor.py`, `tests/security/test_review_tool_runs.py`, `tests/security/test_security_semgrep.py`, `tests/commands/test_security_bandit.py`, `tests/ai/review/test_review_security_tools.py`
- Document: `docs/SELF_IMPROVEMENT.md` (Tool Run Records)

## Feasibility

I ran these commands with git 2.55.0, in a new checkout, in a directory with no checkout and in a directory with an empty `.git` (`git -C <dir> --no-optional-locks <command>`, the form that `_git` uses):

| Command | Case | Result |
| :--- | :--- | :--- |
| `remote get-url origin` | checkout with no remote | exit 2, `error: No such remote 'origin'` |
| `remote get-url origin` | directory with no checkout | exit 128, `fatal: not a git repository` |
| `config --get remote.origin.url` | directory with no checkout, no global `remote.origin.url` | exit 1, no output |
| `config --get remote.origin.url` | directory with no checkout, global config (`GIT_CONFIG_GLOBAL`) sets `remote.origin.url` to `https://example.com/global.git` | exit 0, `https://example.com/global.git` |
| `config --local --get remote.origin.url` | same directory and global config | exit 128, `fatal: --local can only be used inside a git repository` |
| `config --local --get remote.origin.url` | checkout with no remote | exit 1, no output |
| `config --local --get remote.origin.url` | directory with no checkout | exit 128, `fatal: --local can only be used inside a git repository` |
| `config --local --get remote.origin.url` | directory with an empty `.git` | exit 128, same message |
| `config --local --get remote.origin.url` | remote `https://user:token@example.com/a/b.git` | exit 0, URL with the userinfo |

- `_git` in `src/devops_cli/security/tool_executor.py` raises `SandboxError` when the exit code is not in `accepted`. So the plan reads the remote with `config --local --get remote.origin.url` and accepts exit code 0 and 1. The `git config` manual documents exit code 1 for a key that is not set. The command `remote get-url origin` exits with 2 for a missing remote, and git does not document that code. The option `--local` keeps git from reading the global configuration, and it gives exit 128 for a tree that git cannot read, as the commit read does.
- `_tree_commit` already turns a `SandboxError` into None when `required` is false. `_read_tree_commit` already returns None when `nearest_checkout` finds no checkout. The repository read reuses both guards.
- `urlsplit` gives an empty scheme for `git@example.com:a/b.git` and for `/srv/a.git`, and an empty host for `file:///srv/a.git`. It gives scheme `ssh` and the user name `git` for `ssh://git@example.com/a/b.git`.
- `urlsplit('https://[bad/a.git')` and `urlsplit('https://host]/a.git')` raise `ValueError: Invalid IPv6 URL` (`python3 -I`). So the read catches `ValueError` and gives None.
- `run.versionControlProvenance` is an array with `uniqueItems` in the vendored schema `tests/fixtures/sarif-schema-2.1.0.json`. So one run can hold more than one entry. `repositoryUri` is the only required property of an entry, and it has the format `uri`.
- I tested the planned read in a scratch copy of the branch: `_read_repository_uri`, `_tree_repository_uri`, the field and the `record_tool_run` call, as the tasks write them, and no other change. I ran `uv run pytest -n4 tests/security tests/ai`, and the rest of `tests`. Ten tests failed that pass on the base. `GitFake` calls `pytest.fail` for a git command with no record, and each of these files has its own git answers, which have none for `config`:
  - `tests/security/test_scanner_tool_executor.py`: `test_the_tree_of_a_request_is_the_checkout_that_holds_the_targets`, `test_a_request_names_a_relative_target_by_its_absolute_path`, `test_a_scan_of_a_checkout_that_git_cannot_read_still_runs`
  - `tests/security/test_security_semgrep.py`: `test_a_reviews_semgrep_scan_names_only_targets_under_its_working_directory`, `test_semgrep_findings_carry_the_reviewed_trees_paths_and_lines`, `test_a_semgrep_timeout_loses_only_its_batch`, `test_a_review_shows_the_files_semgrep_left_out_in_its_coverage_and_analyzer_sections`
  - `tests/commands/test_security_bandit.py`: `test_the_scan_report_runs_bandit_on_this_repository_with_the_gate_s_config`
  - `tests/ai/review/test_review_security_tools.py`: `test_pipeline_multi_scanner_aggregation`
  - `tests/security/test_review_tool_runs.py`: `test_a_review_profile_holds_one_row_per_tool_run_with_every_field`. Its git answer gives `config` an empty output, so `repository_uri` is None in every row, and the test rejects a `None` field.
  With an answer for `config` in each file (exit 1 with no output, and the URL `https://example.com/a/b.git` in `test_review_tool_runs.py`), the same five files and `tests/ai/test_tool_executor_contract.py` pass. Two other tests fail on the base in this devcontainer, with and without the change: `test_the_direct_executor_refuses_a_network_profile_before_it_starts_the_tool[direct]` (the Popeye binary is missing) and `tests/commands/test_devcontainer_install_tools_dry_run.py::test_mark_only_commands_under_global_dry_run`.
- The tests of `tests/ai/test_tool_executor_contract.py` start git only through the git fake (`_handle_tool_executor_git`). That handler answers `config` with an empty output and exit 0 today, so the handler gets a branch for the new command.

## Existing Tool Considered

The standard library (`urllib.parse`) and the git command cover the need. No other tool is needed. The change extends the existing ToolRun record and SARIF export in src/devops_cli/security/. No internal code is deleted.
