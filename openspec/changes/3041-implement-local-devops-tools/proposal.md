# Proposal

## Why

The implement agent runs the commands of the project with `uv run`, and the shell already allows `uv`. The prompt of the step names only one of them, `uv run devops ci test <file>`. The agent does not know that `devops ai repomap`, `devops ai ast`, `devops docs generate` and `devops openspec check` are safe to run in the shell, so it guesses or uses the general programs (#3041).

The part of #3041 that other issues hold is not in this change: the runner tools `kubectl` and `kube-linter` (#3562), the scoped credential for `devops review` and `devops ai rag-query` (#3563), and the scoped writes with the refusal budget (#3565). The shell table, the refusal hint and the consistency tests of #3072 (PR #3111) already exist.

## What Changes

- `src/devops_cli/roadmap/implement_shell_policy.py` gains `LOCAL_COMMANDS`, one typed table of the `devops` commands that the agent runs through `uv run`: `ci test`, `ai repomap`, `ai ast`, `docs generate` and `openspec check`. Each entry has an access class (`read` or `write`) and a use. No entry has the access `network`.
- `local_commands_table()` renders the table, and `fill_prompt` fills a third placeholder, `{{local_commands}}`, in `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- `docs/ROADMAP_WORKFLOW.md` holds the same table in the section "The shell of a step".
- Tests fail when the table, the prompt and the document differ, when a cataloged command is not a command of the `devops` app, and when a call of a cataloged command is refused or counted as a refusal.
- The `roadmap-implement-step` capability gains one requirement, because the prompt of the step is observable to the agent.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: The prompt lists the local devops commands

## Impact

- Code: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_implement_shell_policy.py`

## Feasibility

- The comment of 2026-11-05 on #3041 and the refine round (moved parts to #3562, #3563 and #3565) leave this part. It was checked against `origin/main` at `be31875c`: `SHELL_PROGRAMS` and `SHELL_REFUSALS` exist in `src/devops_cli/roadmap/implement_shell_policy.py`, and the prompt names only `uv run devops ci test` as a local command. No table lists the other four.
- `uv` is a program of `SHELL_PROGRAMS` with the access `network`, so `uv run devops ...` passes the first-word check of the shell today. A cataloged call is therefore never a refusal, and the change adds a test that pins this.
- `uv run devops ai --help`, `uv run devops ai ast --help` (commands `parse` and `graph`), `uv run devops ai repomap --help`, `uv run devops docs generate` (listed by `uv run devops docs --help`) and `uv run devops openspec check --help` all run from this checkout. `ai ast`, `ai repomap` and `openspec check` read files and make no network call. `docs generate` writes Markdown files in the checkout. `ci test` runs the tests and writes cache files in the checkout.
- The part of the issue that needs a sandbox or a credential is not built here: #3562, #3563 and #3565 hold it.

## Existing Tool Considered

open-policy-agent/opa (Apache-2.0, maintained) decides allow or deny by tool name and arguments. It has no table that the prompt and the documents read, no refusal counter and no tool list for the model, and the shell guard already is a typed Python table with these parts. The change extends that table and adds no dependency. It deletes no code. The written cost is about 10,000 tokens to build and test, about 2,000 tokens a month to keep it, and 2 hours.

## Dependencies

None.
