# Proposal

## Why

Issue #1847: the owner decided on 2026-10-23 that new work uses OpenSpec, and ADR 0010 makes an OpenSpec change folder the record of an item. But `devops pr check-readiness` required a task file in `docs/agent/tasks/`, so no item could use a change folder as its record, and two records for one item give two sources of truth. This change also delivers the rest of #1846: readiness checks the archived folder.

## What Changes

- `devops pr check-readiness` requires a pull request to add `openspec/changes/archive/<date>-<issue>-<slug>/` for the one issue it closes. `uv run devops openspec archive <change>` writes that folder in the last commit of the pull request. The blocker names the expected folder and the archive command.
- Readiness blocks a pull request that changes a file in `openspec/specs/` and adds no archived folder of its own issue. It also blocks a pull request that changes a file in `openspec/changes/archive/` outside the archived folder of its own issue.
- The rule applies where the base holds `openspec/changes/`, in place of `docs/agent/tasks/`. A failing `openspec` check run, which fails an archived change with an unticked task, already blocks through the check-run rule.
- The closed grammars of the active folder and of the archived folder are in `config/constants.py`.
- Removed: the task-file predicate, `CONST_AGENT_TASKS_DIR`, `CONST_AGENT_TASK_FILE_RE`, the task-file messages, `tests/test_agent_task_files.py`, its baseline, `docs/agent/tasks/` with its template, and each sentence in the documents that names the task files as a current record. Git history keeps the old task files. A decommission test keeps the directory out of `src/`, `tests/`, `k8s/`, `.github/` and the hand-written documents.
- AGENTS.md, the pull request template, `CONTEXT.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, `docs/TESTING.md`, `docs/agent/README.md`, the knowledge base, review routing and the generated references name change folders only.
- The change alters what a `devops` command reports, so it carries a spec delta.
- The change fits one pull request. Readiness, the documents and the tests must not disagree, so they change together.

## Capabilities

### New Capabilities

- `pr-grounding`: what `devops pr check-readiness` requires of a pull request, so that the pull request delivers one item and records that item as an archived change folder.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/pr.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py` and the docstring of `src/devops_cli/review/targets.py`.
- A pull request that is open when this change merges converts its task file into a change folder when it updates from `main`.
- Readiness sends the same number of GitHub requests: the base probe reads `openspec/changes` in place of `docs/agent/tasks`.

## Feasibility

- OpenSpec 1.14.3 (`openspec --version`) is the pin in `tools.lock`. In this change, `uv run devops openspec archive 1847-openspec-change-folders` wrote `openspec/changes/archive/2026-10-23-1847-openspec-change-folders/` and `openspec/specs/pr-grounding/spec.md`, and its `openspec validate --all --strict` passed.
- In a scratch repository with the opt-outs set, `openspec archive <change> --yes` archived a change with one unticked task and only warned. Then `openspec validate --archived` printed `1 incomplete task (1/2 completed)` and exited 1. So the `openspec` row of `devops ci` fails such a change, and readiness does not read `tasks.md`.
- `devops gh api --silent "repos/dan-petty/devops-cli/contents/openspec/changes?ref=main"` exited 0, because `openspec/changes/archive/.gitkeep` is tracked. The same read of a missing path answered `HTTP 404`. So the base probe keeps its two answers.
- GitHub's `pulls/{n}/files` reports each file as `added`, `removed`, `modified`, `renamed`, `copied`, `changed` or `unchanged` (GitHub REST documentation). The archive of a folder that the pull request added shows as `added`. The archive of a folder that the base holds shows as `renamed`.
- `devops roadmap close` and its closing comment were deleted with ADR 0013, so readiness is the only code that read task files.

## Existing Tool Considered

OpenSpec, pinned in `tools.lock`, is the record. Its `archive` command writes the archived folder and the living specs, and `openspec validate --archived` fails an archived change with an unticked task. No open tool reads the changed paths of a pull request against the issue that it closes, so the readiness predicate stays our own code. It is two predicates over the file list that readiness already reads. The cost to build and test it is about 40,000 tokens and one hour, and the cost to keep it is a few thousand tokens a year.

The change deletes this internal code: `_writes_task_file`, `_changes_its_task_file` and `_base_has_task_files` in `commands/pr.py`; `CONST_AGENT_TASKS_DIR`, `CONST_AGENT_TASK_FILE_RE` and `CONST_PR_FILE_WRITTEN_STATUSES`; the messages `grounding_task_file_missing` and `grounding_tasks_dir_unread`; `tests/test_agent_task_files.py` and `tests/fixtures/task_files_baseline.txt`; and the task files with their template.
