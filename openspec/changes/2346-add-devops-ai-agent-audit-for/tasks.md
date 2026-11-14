# Tasks

## 1. Read the transcripts and sanitize each kept line

Kind: behavior. Reads: `src/devops_cli/security/sanitizer.py`. Changes: `src/devops_cli/ai/agent_audit/__init__.py` (new), `src/devops_cli/ai/agent_audit/transcript.py` (new), `tests/ai/agent_audit/__init__.py` (new), `tests/ai/agent_audit/conftest.py` (new), `tests/ai/agent_audit/test_transcript.py` (new).

- [x] 1.1 Write `tests/ai/agent_audit/test_transcript.py::test_unknown_record_type_does_not_stop_the_reader` first: it fails because the reader raises on a record of type `api-request-blob`
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_transcript.py` fails on the base
- [x] 1.2 Add the package `src/devops_cli/ai/agent_audit/__init__.py` and the module `src/devops_cli/ai/agent_audit/transcript.py`. Add test package files `tests/ai/agent_audit/__init__.py` and `tests/ai/agent_audit/conftest.py`. `read_transcripts(paths, since_days)` filters files by modification time and streams JSONL lines. Subagent transcripts under `<session>/subagents/` roll into their parent session. The reader keeps tool-use and tool-result records, returning session, file, line, timestamp, command, and output. An unknown record type is skipped and counted, never raised. Each kept line passes through `mask_secrets`, `mask_private_hosts`, and email scrubbing before leaving the reader. Write `test_tokens_emails_and_private_hosts_are_masked`, `test_subagent_transcripts_roll_into_parent_session`, and `test_mtime_filter_skips_older_files`
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_transcript.py` passes

## 2. Reduce commands and failures to signatures

Kind: behavior. Reads: `src/devops_cli/ai/agent_audit/transcript.py`. Changes: `src/devops_cli/ai/agent_audit/signature.py` (new), `tests/ai/agent_audit/test_signature.py` (new).

- [x] 2.1 Write `tests/ai/agent_audit/test_signature.py::test_paths_and_numbers_are_replaced` first: it fails because two commands differing in a path and number produce distinct signatures
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_signature.py` fails on the base
- [x] 2.2 Add `src/devops_cli/ai/agent_audit/signature.py`. `command_signature(text)` retains the program, subcommand, and flags while replacing numbers, paths, and values with placeholders. `error_signature(exit_status, first_error_line)` normalizes the first error line and retains the exit code. Extract exit status from `tool_result` content blocks using `is_error` and exit code lines. Write `test_tool_result_exit_status_extraction`
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_signature.py` passes

## 3. Count the findings across sessions and rank them

Kind: behavior. Reads: `src/devops_cli/ai/agent_audit/signature.py`. Changes: `src/devops_cli/ai/agent_audit/finding.py` (new), `src/devops_cli/ai/agent_audit/report.py` (new), `tests/ai/agent_audit/test_findings.py` (new).

- [x] 3.1 Write `tests/ai/agent_audit/test_findings.py::test_one_finding_for_three_sessions` first: it fails because three sessions produce three separate findings
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_findings.py` fails on the base
- [x] 3.2 Add `src/devops_cli/ai/agent_audit/finding.py` and `src/devops_cli/ai/agent_audit/report.py`. `build_findings(records)` groups records by signature across sessions, counting sessions, recurrences, and elapsed time with one pointer per session. `rank_findings(findings)` orders by session count, then recurrences, then time spent. `render_report(findings, format)` produces formatted table or JSON containing only sanitized text
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_findings.py` passes

## 4. Store the counts of the day and keep a second run unchanged

Kind: behavior. Reads: `src/devops_cli/core/repo.py`, `src/devops_cli/ai/agent_audit/finding.py`. Changes: `src/devops_cli/ai/agent_audit/store.py` (new), `tests/ai/agent_audit/test_store.py` (new).

- [x] 4.1 Write `tests/ai/agent_audit/test_store.py::test_a_second_run_keeps_the_count` first: it fails because a second run increments counts
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_store.py` fails on the base
- [x] 4.2 Add `src/devops_cli/ai/agent_audit/store.py`. `store_path(day)` resolves date files under store name `agent/audit` via `resolve_store_path`. `merge_counts(path, findings)` adds only unseen session files and line numbers, preserving existing counts idempotently. The file holds signatures, counts, and pointers without raw lines, and text is sanitized before writing
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_store.py` passes

## 5. Mark a warning that an open issue names as tracked

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/ai/agent_audit/finding.py`. Changes: `src/devops_cli/ai/agent_audit/tracked.py` (new), `tests/ai/agent_audit/test_tracked.py` (new).

- [x] 5.1 Write `tests/ai/agent_audit/test_tracked.py::test_warning_named_by_an_open_issue_is_tracked` first: it fails because tracked warnings are reported as new
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_tracked.py` fails on the base
- [x] 5.2 Add `src/devops_cli/ai/agent_audit/tracked.py`. Define `TrackedIssues` protocol with `open_issues()`. `GitHubTrackedIssues` reads open issues via `get_roadmap_store`. `mark_tracked(findings, issues)` normalizes warning and issue text, marking matching findings as tracked so they render separately
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_tracked.py` passes

## 6. Group the findings with one model call at a time

Kind: behavior. Reads: `src/devops_cli/roadmap/intake/intake_model.py`, `.github/ISSUE_TEMPLATE/feature_request.yml`, `.github/ISSUE_TEMPLATE/bug_report.yml`. Changes: `src/devops_cli/ai/agent_audit/grouping.py` (new), `tests/ai/agent_audit/test_grouping.py` (new).

- [x] 6.1 Write `tests/ai/agent_audit/test_grouping.py::test_only_masked_signatures_reach_the_model` first: it fails because unmasked signatures reach the model request
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_grouping.py` fails on the base
- [x] 6.2 Add `src/devops_cli/ai/agent_audit/grouping.py`. `group_findings(findings, client)` makes one `chat_structured` call at a time with masked signatures, attaching returned groups to findings. `draft_body(group)` produces issue drafts matching issue template structures. The client uses `get_llm_client` with task analysis
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_grouping.py` passes

## 7. Read the shell history and the agent files as named sources

Kind: behavior. Reads: `src/devops_cli/ai/agent_audit/transcript.py`. Changes: `src/devops_cli/ai/agent_audit/sources.py` (new), `src/devops_cli/ai/agent_audit/shell.py` (new), `src/devops_cli/ai/agent_audit/agent_files.py` (new), `tests/ai/agent_audit/test_sources.py` (new), `tests/ai/agent_audit/test_shell.py` (new), `tests/ai/agent_audit/test_agent_files.py` (new).

- [ ] 7.1 Write `tests/ai/agent_audit/test_sources.py::test_source_transcripts_returns_no_shell_path` first: it fails because transcript sources return shell paths
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_sources.py` fails on the base
- [ ] 7.2 Add `src/devops_cli/ai/agent_audit/sources.py`, `src/devops_cli/ai/agent_audit/shell.py`, and `src/devops_cli/ai/agent_audit/agent_files.py`. `source_paths(source, repo_dir, home)` returns files for the requested source. Add `parse_shell_history(path)` supporting zsh extended format `: <epoch>:<seconds>;<command>`. Add `parse_agent_files(dir_path)` reading `.data/agent/` files. Write `tests/ai/agent_audit/test_shell.py` and `tests/ai/agent_audit/test_agent_files.py`
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_sources.py tests/ai/agent_audit/test_shell.py tests/ai/agent_audit/test_agent_files.py` passes

## 8. File each draft through devops roadmap intake

Kind: behavior. Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/ai/agent_audit/grouping.py`. Changes: `src/devops_cli/ai/agent_audit/filing.py` (new), `src/devops_cli/exceptions/__init__.py`, `tests/ai/agent_audit/test_filing.py` (new).

- [ ] 8.1 Write `tests/ai/agent_audit/test_filing.py::test_confirm_files_one_draft_for_each_group` first: it fails because no drafts are filed
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_filing.py` fails on the base
- [ ] 8.2 Add `src/devops_cli/ai/agent_audit/filing.py` and define typed exception `AgentAuditFilingError` in `src/devops_cli/exceptions/__init__.py`. `file_drafts(drafts, runner)` writes temporary body files and invokes bounded `devops roadmap intake --title <title> --body-file <file> --confirm` processes, reporting filed issue numbers. On failure, raise `AgentAuditFilingError` and stop
  - Verification: `$ uv run devops ci test tests/ai/agent_audit/test_filing.py` passes

## 9. Add the agent-audit command with its modes

Kind: behavior. Reads: `src/devops_cli/commands/ai.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/agent_audit/report.py`, `src/devops_cli/ai/agent_audit/store.py`, `src/devops_cli/ai/agent_audit/tracked.py`, `src/devops_cli/ai/agent_audit/grouping.py`, `src/devops_cli/ai/agent_audit/sources.py`, `src/devops_cli/ai/agent_audit/filing.py`. Changes: `src/devops_cli/commands/ai_agent_audit.py` (new), `src/devops_cli/commands/ai.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_ai_agent_audit.py` (new).

- [ ] 9.1 Write `tests/commands/test_ai_agent_audit.py::test_confirm_calls_file_drafts_once` first: it fails because the command does not exist
  - Verification: `$ uv run devops ci test tests/commands/test_ai_agent_audit.py` fails on the base
- [ ] 9.2 Add `src/devops_cli/commands/ai_agent_audit.py` with options `--since`, `--source`, `--repo-dir`, `--json`, `--plan`, `--confirm`, and `--dry-run`, decorated with `@dry_run_class("request-plan")`. Register the command with `@app.command("agent-audit")` in `src/devops_cli/commands/ai.py`. Add localized messages in `src/devops_cli/lang/en/messages.py` and help entries in `src/devops_cli/lang/en/help.py`. Refuse `--dry-run` with `--confirm`, verified by `test_dry_run_with_confirm_is_refused`. Wire `--confirm` to `file_drafts`
  - Verification: `$ uv run devops ci test tests/commands/test_ai_agent_audit.py` passes

## 10. Regenerate the command reference

Kind: other. Reads: `src/devops_cli/commands/ai_agent_audit.py`. Changes: `docs/CLI_REFERENCE.md`, `docs/commands/ai.md`.

- [ ] 10.1 Run `uv run devops docs generate` and commit regenerated `docs/CLI_REFERENCE.md` and `docs/commands/ai.md`
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
