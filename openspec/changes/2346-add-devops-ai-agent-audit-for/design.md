# Design

## Decisions

- **Add the new capability `agent-audit` instead of modifying existing capabilities.**:
  No existing capability covers session transcripts, signatures, or cross-session problem counts.
  Existing AI capabilities cover gateway models, prompts, and spend tracking.
- **Register the command directly with `@app.command("agent-audit")` in `commands/ai.py`.**:
  Using `app.add_typer` creates an unwanted subcommand group that requires `devops ai agent-audit run`.
  Registering directly with `@app.command("agent-audit")` provides the clean syntax `devops ai agent-audit [options]`.
- **Stream transcripts and filter files by modification time.**:
  Transcripts can exceed 7.7 GB across 5,000 subagent files.
  The reader streams JSONL lines and skips files older than `--since`.
  This design guarantees execution within the 5-minute limit of AGENTS.md rule 5.
- **Roll subagent transcripts into the parent session ID.**:
  Transcripts in subagent folders belong to their parent top-level session.
  Counting them under the parent session preserves accurate cross-session recurrence ranking.
- **Extract exit status from `tool_result` blocks.**:
  Bash tool execution records exit status in the tool result block.
  The parser extracts status from `is_error` and exit code lines.
- **Sanitize secrets, private hostnames, addresses, and emails before storing or sending data.**:
  All kept lines pass through `mask_secrets`, `mask_private_hosts`, and email scrubbing.
  Internal hostnames, private IPs, and personal data never reach models or GitHub issues.
  This enforces AGENTS.md rule 10 and SECURITY.md rule 13.
- **Parse shell history and agent files as distinct sources.**:
  Dedicated parsers handle the zsh extended format `: <epoch>:<seconds>;<command>` and agent files under `.data/agent/`.
- **Resolve the store path with `resolve_store_path` under `agent/audit`.**:
  `resolve_store_path` honors `data.dir` and prevents hardcoded path invariants.
- **Count a session and a line once, merging into the date file.**:
  A second run over identical files preserves existing counts idempotently.
- **Run the model stage with one `get_llm_client` call at a time sending masked signatures only.**:
  ADR 0005 puts finding logic in deterministic tools and uses models only for grouping.
  AGENTS.md rule 7 allows one `devops ai` call at a time.
- **File candidate drafts through `devops roadmap intake --confirm`.**:
  Intake serves as the single entry point to flag duplicates and retain candidates.
- **Refuse `--dry-run` combined with `--confirm`.**:
  The flags contradict each other and raise a usage error.
- **Default `--source` to transcripts and `--since` to 30 days.**:
  Transcripts provide the richest telemetry pairing commands with outputs and exit statuses.

## Rejected alternatives

- **Store the audit in a SQLite database.**:
  Rejected. JSON files per date in the standard library suffice without migrations.
- **Send raw transcript lines to the model.**:
  Rejected. Raw lines contain prompt text, file contents, and potential PII.
  SECURITY.md rule 13 and ADR 0005 require sending masked signatures only.
- **Use `app.add_typer` for a single command.**:
  Rejected. It creates an unnecessary nested subcommand level in Typer.
- **Rely only on `mask_secrets` without host and email masking.**:
  Rejected. `mask_secrets` only masks token patterns and leaves internal IPs, hosts, and emails exposed.
- **Read all sources on every run by default.**:
  Rejected. Shell history and agent files lack exit statuses and add noise.

## Security

Transcripts hold sensitive prompt content and system state.
Every kept line passes through `mask_secrets`, `mask_private_hosts`, and email scrubbing.
Only masked signatures, counts, and pointers enter the report, store, and model requests.
No raw transcript line, secret, internal hostname, private IP, or email leaves the host.
This satisfies AGENTS.md rule 10 and SECURITY.md rule 13.
Automated tests verify that tokens, private IPs, local hostnames, and emails are masked.
