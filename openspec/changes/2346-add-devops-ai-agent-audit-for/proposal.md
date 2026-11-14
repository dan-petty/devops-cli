# Proposal

## Why

The same problems come back in session after session of this project: a warning that every run prints, a command that agents get wrong in the same way, and a manual sequence that should be one command. Nothing counts them, so none of them becomes an issue until a person notices, and AGENTS.md rule 11 asks for an issue for each such problem (#2346).

## What Changes

- Add the `agent-audit` command to the `ai` group with `--since`, `--source`, `--repo-dir`, `--json`, `--plan`, `--confirm` and `--dry-run`, and `--plan` as the default mode.
- Read the Claude Code transcripts of the repository and of its worktrees, skip a record type that the parser does not know, and pass each kept line through `mask_secrets`.
- Reduce each command to a signature and each failure to an error signature, and count them across sessions with one pointer for each session.
- Rank a finding by its sessions, then its recurrences, then its time spent, and print the masked report.
- Write the counts to one JSON file per UTC date under the agent data folder, and keep a second run over the same files from changing them.
- Mark a `devops` warning that an open issue names as tracked, so the report lists it apart from the new findings.
- Group related findings with one model call over masked signatures only, and draft an issue body in the shape of the issue templates.
- File each draft through `devops roadmap intake --confirm`; `--plan` files nothing and `--dry-run` lists the requests and makes none.
- Refuse a run that holds both `--dry-run` and `--confirm`, and read only the named source, which defaults to transcripts.
- Regenerate `docs/CLI_REFERENCE.md` and `docs/commands/ai.md` so the index and the `ai` group page list the new command and its options.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `agent-audit`: Cross-session failure count, Secret masking in report and store, Unknown record type, Idempotent stored counts, Warning named by an open issue, Dry run makes no request, Refused flag pair, Model stage grouping, Ranking by sessions, Default source, Confirm files each draft through intake

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/agent_audit/__init__.py`, `src/devops_cli/ai/agent_audit/transcript.py`, `src/devops_cli/ai/agent_audit/signature.py`, `src/devops_cli/ai/agent_audit/finding.py`, `src/devops_cli/ai/agent_audit/report.py`, `src/devops_cli/ai/agent_audit/store.py`, `src/devops_cli/ai/agent_audit/tracked.py`, `src/devops_cli/ai/agent_audit/grouping.py`, `src/devops_cli/ai/agent_audit/sources.py`, `src/devops_cli/ai/agent_audit/filing.py`, `src/devops_cli/commands/ai_agent_audit.py`, `src/devops_cli/commands/ai.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/CLI_REFERENCE.md`, `docs/commands/ai.md`
- Tests: `tests/ai/agent_audit/test_transcript.py`, `tests/ai/agent_audit/test_signature.py`, `tests/ai/agent_audit/test_findings.py`, `tests/ai/agent_audit/test_store.py`, `tests/ai/agent_audit/test_tracked.py`, `tests/ai/agent_audit/test_grouping.py`, `tests/ai/agent_audit/test_sources.py`, `tests/ai/agent_audit/test_filing.py`, `tests/commands/test_ai_agent_audit.py`

## Feasibility

- The probe confirms the cited instructions file, word for word: The path `AGENTS.md` is a file of the staging commit.
- The probe shows that the issue cites the mask module at a root path that no commit holds: The path `security/sanitizer.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/security/sanitizer.py`. No commit in the history deleted or renamed it, so the plan cites the real module and plans no compensating code.
- The probe shows the same for the issue template: The path `feature_request.yml` is no file at the root of the staging commit. These files of the commit are candidates: `.github/ISSUE_TEMPLATE/feature_request.yml`.
- The probe shows that the config audit trail is no file of the checkout: The path `.data/logs/audit.jsonl` is no file of the staging commit. No commit in the history deleted or renamed it. The issue rejects that file as a source, and the plan reads no such file.
- The host counts of the issue are `not checked`: the 22 session files, the 1219 shell-history lines, the 883 extended entries, the 420 audit records and the 45 agent entries live under the home directory of a host, and this run read the repository only.
- `src/devops_cli/security/sanitizer.py:def mask_secrets` is the mask of the module, and it writes `<masked-github-token>` in place of a `ghp_` token; the reader, the store and the model request call it.
- `src/devops_cli/ai/controller/manager.py:117:self.agent_dir = self.data_dir / "agent"` shows the agent folder of the data directory, which the store reuses.
- `src/devops_cli/core/repo.py:def resolve_store_path` resolves a store name under `data.dir`; the plan calls it and writes no literal data path, which keeps the invariant of #1036.
- `src/devops_cli/commands/roadmap.py:def intake_cmd` is the command that `--confirm` calls, and `src/devops_cli/commands/roadmap.py:159:`"--body-file", exists=True, dir_okay=False, help=HELP.roadmap.intake_body_file`` shows the option that carries the draft body beside `--title` and `--confirm`.
- `src/devops_cli/commands/ci.py:2240:def docs(` is the row that the last group runs as `uv run devops ci docs`.
- `src/devops_cli/roadmap/intake/intake_model.py:class GatewayIntakeModel` shows the one-call shape that the model stage copies: `get_llm_client` with `chat_structured`.
- `src/devops_cli/roadmap/stores/store.py:class RoadmapStore` holds `issues()`, which returns each issue record with its number, title and body, and `src/devops_cli/roadmap/stores/store.py:def get_roadmap_store` gives the store of the repository; the tracked check reads the open issues through them.
- `src/devops_cli/commands/ai.py:127:ast_app,` shows how a command module joins the `ai` group through `app.add_typer`, and `tests/commands/test_ai_cmd.py` is the existing test of that module, which the command group reads.
- First check on the real system: `uv run devops ci test tests/commands/test_ai_agent_audit.py` fails on the base, because no module registers the audit command and the test imports it.
- First check on the real system: `uv run devops ci test tests/ai/agent_audit/test_transcript.py` fails on the base, because the reader does not exist.
- First check on the real system: `uv run devops ci docs` fails after the command registers and before `uv run devops docs generate` rewrites the reference pages.
- `get_roadmap_store(repo)` needs a client of GitHub, because the open issues and their bodies come from the repository.
- `get_llm_client(task="analysis", ...)` needs a client of the AI gateway and the API key from the keyring; the tests pass a stub client.
- `load_settings()` needs a checkout of the repository for its config file; the tests pass a settings object.
- `resolve_store_path("agent/audit")` needs a checkout of the repository, because the agent folder resolves under the main worktree.
- The subprocess `devops roadmap intake --confirm` needs a network and a client of GitHub; `--plan` and `--dry-run` start it never.
- `mask_secrets(text)` needs no checkout, no client and no network: it is a pure function of its text.
- The plan introduces no verify program: each `verify` is `uv run devops ci test` on a test file or `uv run devops ci docs`, which the image runs with `uv` and `pytest`, so no failure class is new and no pod setting changes.
- The image lists `zsh` as `NOT_IN_RUNNER`, so no test reads a real zsh history; the shell-history test reads a fixture file under `tmp_path`.
- The pod sets `readOnlyRootFilesystem: true`, so each store test writes under `tmp_path` and the command writes under the data directory.
- `--source` takes 4 values, `transcripts`, `shell`, `files` and `all`: group 7 returns the paths of the named source, and group 9 sets its default to `transcripts`.
- Group 8 creates `src/devops_cli/ai/agent_audit/filing.py` and group 9 reads it, so the command of group 9 calls `file_drafts` from that module when the run holds `--confirm`; `--plan` and `--dry-run` call it never.
- `references("agent-audit")` answered `No line of the commit holds 'agent-audit'`, so the command name is new and no file of the commit needs a change for a rename.
- `find_issues("agent-audit")` lists 10 open items: #2346, this issue, and #5151 (docs site), #5128 (node drain), #5130 (infra apply), #4671 (brain tools), #4848 (gh issue), #5120 (infra repos), #5267 (drain window), #5208 (command gate) and #2176 (mutation test). None of the nine names `src/devops_cli/ai/agent_audit/` or `src/devops_cli/commands/ai_agent_audit.py`, so each is a removed member of the set and `dependencies` is empty.
- The input holds no `rejected_plan`, so no earlier reason needs an answer.

## Existing Tool Considered

daaain/claude-code-log (MIT, maintained) reads the same JSONL transcripts and emits JSON, but it has no command or error signature, no cross-session count or ranking, no secret mask, no open-issue match, no shell-history or agent-file source and no `--plan`, `--confirm` or `--dry-run` mode. Building the reader, the signatures, the ranking, the store and the tests costs 200k tokens and 8 hours, and following changes of the transcript format costs 20k tokens a quarter. The change deletes no existing module.

## Dependencies

None.
