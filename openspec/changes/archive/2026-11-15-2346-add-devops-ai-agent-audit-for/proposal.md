# Proposal

## Why

The same problems return in session after session of this project.
A warning that every run prints, a command that agents get wrong, and a manual sequence return often.
Nothing counts them today.
None of them becomes an issue until a person notices.
AGENTS.md rule 11 asks for an issue for each recurring problem (#2346).
Related work includes #4840, which ranks devops usage errors from the telemetry ledger.

## What Changes

- Add the `agent-audit` command to the `ai` group with `@app.command("agent-audit")`.
- The command supports `--since`, `--source`, `--repo-dir`, `--json`, `--plan`, `--confirm` and `--dry-run`.
- `--plan` is the default execution mode.
- Read Claude Code transcripts of the repository and its worktrees using mtime filtering and streaming.
- Subagent transcripts roll into their parent top-level session.
- Extract tool exit status from `tool_result` blocks using `is_error` and exit code patterns.
- Parse shell history in extended format (`: <epoch>:<seconds>;<command>`) and agent files under `.data/agent/`.
- Sanitize each kept line with `mask_secrets`, `mask_private_hosts`, and PII scrubbing for emails and addresses.
- Reduce each command and failure to normalized signatures.
- Count recurring problems across sessions with one pointer for each session.
- Rank findings by sessions, recurrences, and time spent.
- Store daily counts idempotently under `.data/agent/audit/<date>.json`.
- Mark a warning that an open issue names as tracked.
- Group related findings with one model call at a time using masked signatures only.
- File each draft candidate through `devops roadmap intake --confirm`.
- Refuse `--dry-run` combined with `--confirm`.
- Regenerate `docs/CLI_REFERENCE.md` and `docs/commands/ai.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `agent-audit`: Cross-session failure count, Secret and personal data masking in report and store, Unknown record type, Idempotent stored counts, Warning named by an open issue, Dry run makes no request, Refused flag pair, Model stage grouping, Ranking by sessions, Default source, Shell history and agent file sources, Confirm files each draft through intake.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/agent_audit/__init__.py`, `src/devops_cli/ai/agent_audit/transcript.py`, `src/devops_cli/ai/agent_audit/shell.py`, `src/devops_cli/ai/agent_audit/agent_files.py`, `src/devops_cli/ai/agent_audit/signature.py`, `src/devops_cli/ai/agent_audit/finding.py`, `src/devops_cli/ai/agent_audit/report.py`, `src/devops_cli/ai/agent_audit/store.py`, `src/devops_cli/ai/agent_audit/tracked.py`, `src/devops_cli/ai/agent_audit/grouping.py`, `src/devops_cli/ai/agent_audit/sources.py`, `src/devops_cli/ai/agent_audit/filing.py`, `src/devops_cli/commands/ai_agent_audit.py`, `src/devops_cli/commands/ai.py`, `src/devops_cli/exceptions/__init__.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/CLI_REFERENCE.md`, `docs/commands/ai.md`
- Tests: `tests/ai/agent_audit/__init__.py`, `tests/ai/agent_audit/conftest.py`, `tests/ai/agent_audit/test_transcript.py`, `tests/ai/agent_audit/test_shell.py`, `tests/ai/agent_audit/test_agent_files.py`, `tests/ai/agent_audit/test_signature.py`, `tests/ai/agent_audit/test_findings.py`, `tests/ai/agent_audit/test_store.py`, `tests/ai/agent_audit/test_tracked.py`, `tests/ai/agent_audit/test_grouping.py`, `tests/ai/agent_audit/test_sources.py`, `tests/ai/agent_audit/test_filing.py`, `tests/commands/test_ai_agent_audit.py`

## Feasibility

- The check reads no GitHub state today.
- `mask_secrets` and `mask_private_hosts` live in `src/devops_cli/security/sanitizer.py`.
- An email scrubber removes personal email addresses before storage or model transit.
- Transcripts total 7.7 GB on the host.
- The reader streams JSONL lines and filters files by mtime using `--since`.
- Streaming stays within the 5-minute execution budget of AGENTS.md rule 5.
- Subagent transcripts roll into their parent session to preserve session counts.
- `tool_result` blocks supply the exit status via `is_error` and exit code lines.
- Shell history parsing handles the zsh extended format `: <epoch>:<seconds>;<command>`.
- The command registers directly on the ai app with `@app.command("agent-audit")`.
- Typed error `AgentAuditFilingError` handles filing failures cleanly.
- `devops roadmap intake` serves as the entry point for filing drafts under `--confirm`.
- All tests run offline with mock responses and fixture files.
- The change fits standard runner resources and limits.

## Existing Tool Considered

daaain/claude-code-log (MIT, maintained) reads JSONL transcripts and emits JSON. It lacks command or error signatures, cross-session counting, secret masking, open-issue matching, and filing modes. Building the reader, sanitizer, signatures, and filing costs about 200k tokens and 8 hours.

## Dependencies

None.
