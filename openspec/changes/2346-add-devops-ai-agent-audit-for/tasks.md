# Tasks

## 1. Read the transcripts and mask each kept line

Kind: behavior. Reads: `src/devops_cli/security/sanitizer.py`. Changes: `src/devops_cli/ai/agent_audit/__init__.py` (new), `src/devops_cli/ai/agent_audit/transcript.py` (new), `tests/ai/agent_audit/test_transcript.py` (new).

- [ ] 1.1 Write `tests/ai/agent_audit/test_transcript.py::test_unknown_record_type_does_not_stop_the_reader` first: it fails because the reader raises on a record of type `api-request-blob`
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_transcript.py` fails on the base
- [ ] 1.2 Add the package `src/devops_cli/ai/agent_audit/__init__.py` and the module `src/devops_cli/ai/agent_audit/transcript.py`. `read_transcripts(paths)` opens each JSONL file, keeps the tool-use and tool-result records, and returns one value for each kept record with the file, the line number, the time, the command text and the output text. A record type that the module does not know is skipped and counted, never raised. Each kept text passes `mask_secrets` from `src/devops_cli/security/sanitizer.py` before it leaves the reader
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_transcript.py` passes

## 2. Reduce commands and failures to signatures

Kind: behavior. Reads: `src/devops_cli/ai/agent_audit/transcript.py`. Changes: `src/devops_cli/ai/agent_audit/signature.py` (new), `tests/ai/agent_audit/test_signature.py` (new).

- [ ] 2.1 Write `tests/ai/agent_audit/test_signature.py::test_paths_and_numbers_are_replaced` first: it fails because two commands that differ only in a path and a number give two signatures today
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_signature.py` fails on the base
- [ ] 2.2 Add `src/devops_cli/ai/agent_audit/signature.py`. `command_signature(text)` keeps the program, the subcommand and the flags, and replaces a path, a number and a flag value with a placeholder. `error_signature(exit_status, first_error_line)` normalizes the first error line and keeps the exit status. A command with a zero exit status and no error line gives no error signature
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_signature.py` passes

## 3. Count the findings across sessions and rank them

Kind: behavior. Reads: `src/devops_cli/ai/agent_audit/signature.py`. Changes: `src/devops_cli/ai/agent_audit/finding.py` (new), `src/devops_cli/ai/agent_audit/report.py` (new), `tests/ai/agent_audit/test_findings.py` (new).

- [ ] 3.1 Write `tests/ai/agent_audit/test_findings.py::test_one_finding_for_three_sessions` first: it fails because three sessions give three findings today
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_findings.py` fails on the base
- [ ] 3.2 Add `src/devops_cli/ai/agent_audit/finding.py` and `src/devops_cli/ai/agent_audit/report.py`. `build_findings(records)` groups the records by signature across sessions, counts the sessions, the recurrences and the time spent, and keeps one pointer of file, line and time for each session. `rank_findings(findings)` orders by sessions, then recurrences, then time spent. `render_report(findings, format)` writes the table or the JSON and holds masked text only
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_findings.py` passes

## 4. Store the counts of the day and keep a second run unchanged

Kind: behavior. Reads: `src/devops_cli/core/repo.py`, `src/devops_cli/ai/agent_audit/finding.py`. Changes: `src/devops_cli/ai/agent_audit/store.py` (new), `tests/ai/agent_audit/test_store.py` (new).

- [ ] 4.1 Write `tests/ai/agent_audit/test_store.py::test_a_second_run_keeps_the_count` first: it fails because the second run doubles the count today
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_store.py` fails on the base
- [ ] 4.2 Add `src/devops_cli/ai/agent_audit/store.py`. `store_path(day)` returns the file of the UTC date under the store name agent/audit, resolved with `resolve_store_path` from `src/devops_cli/core/repo.py`. `merge_counts(path, findings)` reads the file, adds only a session file and line number that the file does not hold yet, writes the counts and returns them, so a second run over the same files changes nothing. The file holds the signature, the count and the pointers, and no transcript line, and each text passes `mask_secrets` before the write
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_store.py` passes

## 5. Mark a warning that an open issue names as tracked

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/ai/agent_audit/finding.py`. Changes: `src/devops_cli/ai/agent_audit/tracked.py` (new), `tests/ai/agent_audit/test_tracked.py` (new).

- [ ] 5.1 Write `tests/ai/agent_audit/test_tracked.py::test_warning_named_by_an_open_issue_is_tracked` first: it fails because the warning is reported as new today
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_tracked.py` fails on the base
- [ ] 5.2 Add `src/devops_cli/ai/agent_audit/tracked.py`. `TrackedIssues` is a protocol with `open_issues()`, which returns the number, the title and the body of each open issue. `GitHubTrackedIssues` reads them through `get_roadmap_store` and its `issues()` from `src/devops_cli/roadmap/stores/store.py`. `mark_tracked(findings, issues)` normalizes each warning and each issue text, and sets `tracked` on a finding that an issue names, so the report lists it apart from the new findings. The test passes a stub `TrackedIssues`
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_tracked.py` passes

## 6. Group the findings with one model call at a time

Kind: behavior. Reads: `src/devops_cli/roadmap/intake/intake_model.py`, `.github/ISSUE_TEMPLATE/feature_request.yml`, `.github/ISSUE_TEMPLATE/bug_report.yml`. Changes: `src/devops_cli/ai/agent_audit/grouping.py` (new), `tests/ai/agent_audit/test_grouping.py` (new).

- [ ] 6.1 Write `tests/ai/agent_audit/test_grouping.py::test_only_masked_signatures_reach_the_model` first: it fails because the request holds a raw line today
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_grouping.py` fails on the base
- [ ] 6.2 Add `src/devops_cli/ai/agent_audit/grouping.py`. `group_findings(findings, client)` makes one `chat_structured` call at a time with the masked signatures and a schema of groups, and attaches each returned group to its findings. `draft_body(group)` writes the body in the shape of `.github/ISSUE_TEMPLATE/feature_request.yml` or `.github/ISSUE_TEMPLATE/bug_report.yml`. The client comes from `get_llm_client` with the task analysis, and the test passes a stub client that records its request
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_grouping.py` passes

## 7. Read the shell history and the agent files as named sources

Kind: behavior. Reads: `src/devops_cli/ai/agent_audit/transcript.py`. Changes: `src/devops_cli/ai/agent_audit/sources.py` (new), `tests/ai/agent_audit/test_sources.py` (new).

- [ ] 7.1 Write `tests/ai/agent_audit/test_sources.py::test_source_transcripts_returns_no_shell_path` first: it fails because the transcript source returns the shell history today
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_sources.py` fails on the base
- [ ] 7.2 Add `src/devops_cli/ai/agent_audit/sources.py`. `source_paths(source, repo_dir, home)` returns the files to read: the transcript directories of the repository and of its worktrees for transcripts, the zsh history of the home directory for shell, the entries of the agent folder of the data directory for files, and all of them for all. The function returns no path that the named source does not cover, so a run with no `--source` opens no shell history. The shell-history test reads a fixture file under `tmp_path`
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_sources.py` passes

## 8. File each draft through devops roadmap intake

Kind: behavior. Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/ai/agent_audit/grouping.py`. Changes: `src/devops_cli/ai/agent_audit/filing.py` (new), `tests/ai/agent_audit/test_filing.py` (new).

- [ ] 8.1 Write `tests/ai/agent_audit/test_filing.py::test_confirm_files_one_draft_for_each_group` first: it fails because no draft is filed today
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_filing.py` fails on the base
- [ ] 8.2 Add `src/devops_cli/ai/agent_audit/filing.py`. `file_drafts(drafts, runner)` writes each draft body to a temporary file and starts one bounded `devops roadmap intake --title <title> --body-file <file> --confirm` process for it, through the given runner, and reports each filed number. A failure of one draft names it and stops the run. The test passes a stub runner and asserts the argument list. The command group that follows reads this module and calls `file_drafts` for a run with `--confirm`
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_filing.py` passes

## 9. Add the agent-audit command with its modes

Kind: behavior. Reads: `src/devops_cli/commands/ai.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/ai/agent_audit/report.py`, `src/devops_cli/ai/agent_audit/store.py`, `src/devops_cli/ai/agent_audit/tracked.py`, `src/devops_cli/ai/agent_audit/grouping.py`, `src/devops_cli/ai/agent_audit/sources.py`, `src/devops_cli/ai/agent_audit/filing.py`, `tests/commands/test_ai_cmd.py`. Changes: `src/devops_cli/commands/ai_agent_audit.py` (new), `src/devops_cli/commands/ai.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_ai_agent_audit.py` (new).

- [ ] 9.1 Write `tests/commands/test_ai_agent_audit.py::test_confirm_calls_file_drafts_once` first: it fails because the command does not exist today
  - Verification: `$ uv run devops ci test tests/commands/test_ai_agent_audit.py` fails on the base
- [ ] 9.2 Add `src/devops_cli/commands/ai_agent_audit.py` with the options `--since`, `--source`, `--repo-dir`, `--json`, `--plan`, `--confirm` and `--dry-run`, and declare it with `@dry_run_class("request-plan")`. A run with `--dry-run` and `--confirm` exits with a usage error and files nothing, which `tests/commands/test_ai_agent_audit.py::test_dry_run_with_confirm_is_refused` asserts. `--confirm` calls `file_drafts` from `src/devops_cli/ai/agent_audit/filing.py` with the drafted groups of the model stage and a bounded runner, and prints each filed number. `--dry-run` lists the requests and the paths it would read, and makes no request. `--plan` prints the report and files nothing. Join the module to the `ai` group with `app.add_typer` under the name `agent-audit`, as `src/devops_cli/commands/ai.py:127:ast_app,` joins a sub-app, and add the help entry to `src/devops_cli/lang/en/help.py`. Read `tests/commands/test_ai_cmd.py` and keep its rows true
  - Verification: `$ uv run devops ci test tests/commands/test_ai_agent_audit.py` passes

## 10. Regenerate the command reference

Kind: other. Reads: `src/devops_cli/commands/ai_agent_audit.py`. Changes: `docs/CLI_REFERENCE.md`, `docs/commands/ai.md`.

- [ ] 10.1 Run `uv run devops docs generate` and commit the regenerated `docs/CLI_REFERENCE.md` and `docs/commands/ai.md`, which then list the new command and its options in the command matrix and on the `ai` group page
  - Verification: `$ uv run devops ci docs` passes
- [ ] 10.2 Regenerate `docs/CLI_REFERENCE.md` and `docs/commands/ai.md` with `uv run devops docs generate`, so the index and the `ai` group page list the new command and its options
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: A failing signature that occurs in three sessions appears once, with a count of 3 and a pointer for each session.
- Group 4: A secret in a fixture line is masked in the report and in the stored counts.
- Group 1: A record type that the parser does not know does not stop the run.
- Group 4: A second run over the same files does not change the stored counts.
- Group 5: A `devops` warning that an open issue names is not reported as new.
- Group 9: `--dry-run` reads no file outside the named sources and makes no request.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
