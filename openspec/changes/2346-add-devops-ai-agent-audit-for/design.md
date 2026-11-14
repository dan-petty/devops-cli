# Design

## Decisions

- **Add the new capability `agent-audit` instead of a requirement of an existing capability.**: No capability in the list covers session transcripts, signatures or a count across sessions; the ai capabilities cover model calls, prompts and spend.
- **Put the audit code in `src/devops_cli/ai/agent_audit/` and the command in `src/devops_cli/commands/ai_agent_audit.py`.**: The command module joins the `ai` group the way `src/devops_cli/commands/ai.py:127:ast_app,` joins a sub-app, and the tests mirror the packages at `tests/ai/agent_audit/` and `tests/commands/`.
- **Resolve the store path with `resolve_store_path` under the store name agent/audit, one file per UTC date.**: `src/devops_cli/core/repo.py:def resolve_store_path` honours `data.dir` and keeps the invariant of #1036, which refuses a literal data path in `src/`.
- **Mask each kept line with `mask_secrets` as the reader returns it, and keep counts, signatures and pointers only.**: `src/devops_cli/security/sanitizer.py:def mask_secrets` turns a `ghp_` token into `<masked-github-token>`, so the report, the store and the model request hold no raw transcript text.
- **Count a session and a line once, by the pair of session file and line number, and merge that pair into the file of the date.**: A second run over the same files then writes the same counts, which is the criterion of the issue.
- **Run the model stage only when the run asks for it, with one `get_llm_client` call at a time, and send masked signatures only.**: ADR 0005 puts the finding in the tool and lets a model group and draft; AGENTS.md rule 13 allows one `devops ai` call at a time.
- **Build the filing module before the command module, and have the command call `file_drafts` when the run holds `--confirm`.**: The command is the only caller of the filing module, so the module exists in an earlier group and the command group reads it and wires the mode to it; otherwise `--confirm` files nothing.
- **File a draft by a bounded subprocess of `devops roadmap intake --title ... --body-file ... --confirm`.**: Intake is the single entry point that flags a possible duplicate and never drops a candidate, and `--plan` and `--dry-run` start no subprocess.
- **Declare the command with `@dry_run_class("request-plan")` and refuse `--dry-run` with `--confirm`.**: A run can file issues and call a model, so it has a request plan; the pair contradicts itself, as `devops roadmap return` already refuses it.
- **Default `--source` to transcripts and `--since` to 30 days.**: The transcripts are the only source that pairs a command with its output and its exit status, and transcripts older than 30 days are already gone.

## Rejected alternatives

- **Store the audit in a SQLite database.**: One JSON file per date holds the counts, and `json` is in the standard library; a schema and a migration would add work for no query that the report makes.
- **Send raw transcript lines to the model.**: A raw line holds prompts, file contents and possibly secrets; SECURITY.md rule 13 and ADR 0005 keep them on the host, and the model needs the signature only.
- **Let the model find and rank the problems.**: ADR 0005 rejects model-found findings: the finding comes from the tool, and the model groups and drafts only.
- **Use `atuin` for the shell history.**: It needs a host install, its import of the existing zsh history carries no exit status, and the image lists `zsh` as `NOT_IN_RUNNER`, so no test can check it.
- **Make `--confirm` the default mode.**: An audit run would file issues with no review of the drafts; the report alone changes nothing, and the project files issues only under `--confirm`.
- **Read all three sources on every run.**: The shell history and the agent files add personal data and repeated commands but no exit status, so a default run reads the one source that carries the signal.

## Security

The audit reads files under the home directory of the host and crosses a trust boundary when it writes the report, the store and the model request: every kept line passes `mask_secrets` before any of the three, and the store holds counts, signatures and pointers only, never a transcript line. A person must confirm that `--source all` may read the shell history and the agent files, and that no secret or personal data leaves the host to a model. `tests/ai/agent_audit/test_transcript.py` and `tests/ai/agent_audit/test_store.py` fail if a `ghp_` token reaches the report or the stored file, and `tests/ai/agent_audit/test_grouping.py` fails if a raw line reaches the model request.
