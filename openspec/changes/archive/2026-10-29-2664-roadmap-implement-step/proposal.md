# Proposal

## Why

Issue #2664, the first sub-issue of #2661. No command runs one task group of a staged change in one bounded context. An agent session runs the whole change with the whole repository in context, so a local model's window overflows and the result depends on the habits of the agent.

`devops roadmap implement --item N --group n` runs one group of the `tasks.md` of item N in a checkout. It builds the inputs of the step, runs one agent with a bounded budget, judges the result with checks that the model does not decide, and commits the group or resets the checkout. It writes nothing to GitHub. A person runs it in a worktree today. The implement job of sub-issue #2665 will run it for each group.

## What Changes

- A new command, `devops roadmap implement --item N --group n [--source <checkout>] [--format table|json] [--dry-run]`, and a new module `roadmap/implement_step.py`.
- A new dependency, `pydantic-ai-harness[coder]==0.59.0`, pinned as `pydantic-ai` is. The harness releases in step with pydantic-ai and pins `pydantic-ai-slim` to its own version number. So the change moves `pydantic-ai` from 2.54.0 to 2.59.0, and `genai-prices` from 0.1.9 to 0.1.13, which `pydantic-ai-slim` 2.59.0 requires. The reason is a security advisory on the older harness releases, as Feasibility records.
- A new task `ai.tasks.implement` with the default model `devops-coder` and `context_window` 128000. `get_task_model("implement")` serves the step.
- The agent is one pydantic-ai `Agent` with `LocalWorkspace(<checkout>)` and `Coder`. The step tunes `Coder` where its parts are public: the shell tool takes an allowlist of `git`, `uv`, `ruff` and `mypy` and runs with a scratch `HOME`, the tool results are cut to a smaller size, and the compaction capabilities get the real window of the task. `delegate_task` is off, so one step is one run.
- The budget is `UsageLimits` with `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` (80) requests and `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` tool calls. The step refuses to start when its inputs measure more than the window minus `CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS`. A run that reaches a limit ends as stopped, with the class of the pydantic-ai error as the reason.
- The exit is judged by the step: every verification command of the group passes, `ruff check`, `ruff format --check` and `mypy --strict` pass on the changed Python files, every task of the group is ticked, no other group changed, and the agent made no commit. Then the step commits as `<group title> (#N)`. Otherwise it resets the checkout to the commit where the step started and reports stopped.
- The instructions of the agent are in `src/devops_cli/ai/tasks/roadmap_implement_step.md`. A knowledge base note describes the harness.
- The step shares two helpers with refine's investigation: the stream drain and the spend record. They move to `roadmap/agent_run.py`.
- A consumer observes a command, a setting and a report, so the change carries spec deltas: a new capability `roadmap-implement-step` and one added requirement in `ai-task-models`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-implement-step`: what `devops roadmap implement` reads, runs, checks, commits and reports.

### Modified Capabilities

- `ai-task-models`: one new requirement, "The implement task serves the step with devops-coder".

## Impact

- `src/devops_cli/roadmap/implement_step.py` (new), `src/devops_cli/roadmap/agent_run.py` (new), `src/devops_cli/roadmap/refine_investigation.py`.
- `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/exceptions/roadmap.py`.
- `src/devops_cli/config/settings.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/commands/ai.py`.
- `src/devops_cli/ai/tasks/roadmap_implement_step.md` (new), `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md` (new).
- `pyproject.toml` and `uv.lock`.
- Documents that `devops docs generate --sync-readme` writes.

## Feasibility

- Version fit, checked on PyPI and in a clean Python 3.14.10 environment. Each release of `pydantic-ai-harness` pins `pydantic-ai-slim` to its own version number: 0.63.0 pins 2.63.0, and 0.54.0 pins 2.54.0. Release 0.54.0 fits the pinned pydantic-ai 2.54.0, and `Coder` ran on it. But `uv audit`, a gate of `devops ci`, reports GHSA-3589-pxp7-3gj8 for 0.54.0: a tool-call limit bypass in nested CodeMode calls, fixed in 0.59.0. The step uses no CodeMode, but the gate cannot be lowered. So the change takes 0.59.0 and moves pydantic-ai to 2.59.0. `pydantic-ai-slim` 2.59.0 requires `genai-prices>=0.1.13`, so that pin moves to 0.1.13, and `uv lock` moves `google-genai` to 2.34.0 with it. 2.63.0 does not resolve with the pins of the project in the same way: it needs the same `genai-prices` move. `uv audit` then reports no vulnerability. The tests that touch pydantic-ai, the spend ledger and the gateway pass on 2.59.0, and the tables of finish reasons that the project copies from pydantic-ai are the same in 2.59.0 as in 2.54.0.
- `Coder` runs on Python 3.14. With `LocalWorkspace(<dir>)` it registers six tools: `read_file`, `write_file`, `edit_file`, `list_files`, `grep` and `shell`. A probe run in a temporary git repository used a pydantic-ai `FunctionModel` as the model. `write_file` wrote a file in the workspace, `shell` ran `git status --short` and returned `?? a.txt`, and the run ended with the model's text. The harness drives the model with streamed requests, so the fake needs a `stream_function`. The test fake of refine's investigation already does this.
- `get_task_model` returns a pydantic-ai `Model`: the client override when it is one, else the model that `resolve_pydantic_ai_model` builds. `Coder` takes any `Model`, so the task model and a `FunctionModel` both work.
- The shell allowlist. `Coder` builds its `Shell` capability with no allowlist. `CombinedCapability.visit_and_replace` is public API of pydantic-ai 2.54.0 and 2.59.0, and it replaces that leaf with `Shell(allowed_commands=[...])`. In the probe, `curl http://example.com` came back to the model as the retry text `Command 'curl' is not in the allowed list.` and the run went on. `git status --short` ran. The harness documents that its checks are best-effort and are not a security boundary. They test the first word of the command, so the step also denies the shell operators that start a second command. The shell is therefore not a boundary. The step hardens what it can: the allowlist leaves out `devops` and `openspec`, which can write to GitHub and to the change, and the shell gets a scratch `HOME` (with `XDG_CONFIG_HOME`, no system git configuration and no password prompt), so that the git configuration, credential helper and keys of the user do not reach it. A command such as `uv run python -c` still runs code. The pod limits and the environment with no credential of the runner (sub-issue 3) are the hard boundary, as the issue says.
- The `ClearToolResults` and `WarnNearLimits` capabilities of `Coder` take a `context_window` field that overrides the registry lookup, and `Coder`'s tool output cut is a `ToolOutputLimits` band. The probe replaced all three with `dataclasses.replace`.
- The gateway window. The issue proposes `max_input_tokens: 128000` on the `devops-coder` route. `k8s/llm/gateway/config.yaml` records that LiteLLM writes a deployment's `model_info` into the cost-map entry that every deployment of the same backend model reads (#1064), and `tests/test_k8s_llm_gateway.py` fails when a group gives `qwen3-coder:30b` a window. `devops-coder` and `devops-review` share that backend, so the window would also bind the review pool. This change does not add it. The step measures its inputs before the first request, which refuses an oversized prompt earlier than the gateway would.
- #2489 (the spend capability) is not in the tree. The step records spend as refine's investigation does, one record for the run.

## Existing Tool Considered

`pydantic-ai-harness` `Coder` and `LocalWorkspace`, and pydantic-ai `UsageLimits`. They give the agent loop, the file and shell tools, the context controls and the limits. The Claude Agent SDK, the Copilot coding agent, OpenHands, SWE-agent and Aider are rejected on #2661.

The change builds only what no tool gives: the parser of the task groups, the inputs of a step, the exit checks, the commit or the reset, and the report. For the parsing it uses `markdown-it-py`, which the project has. It uses `ContextPacker` and `count_tokens` for the file packing and the measure.

Cost of what the change builds, estimated: about 800 lines of code and tests, about 300k tokens of agent work, and one day of elapsed time. Upkeep is a review of each 0.x release of the harness, which can change its API between minor releases. The pin keeps the harness and pydantic-ai in step.

The change deletes the private `_drain` and `_record_spend` of `refine_investigation.py`. It keeps one public copy in `agent_run.py` for both users.
